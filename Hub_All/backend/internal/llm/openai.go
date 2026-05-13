package llm

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"os"
	"regexp"
	"strconv"
	"strings"
	"time"

	"golang.org/x/time/rate"
)

// reTryAgainIn bắt cụm "Please try again in 315ms" / "in 1.2s" trong body 429.
var reTryAgainIn = regexp.MustCompile(`try again in\s+([\d.]+)(ms|s)`)

const (
	maxRateLimitRetries = 5
	maxRateLimitBackoff = 30 * time.Second

	// Mặc định gpt-4o-mini Tier 1 = 200k TPM. Override qua env OPENAI_TPM.
	defaultOpenAITPM = 200_000
	// Số token max_tokens cố định trong request body bên dưới.
	openAIMaxTokens = 2048
	// Hệ số ước lượng token từ ký tự (heuristic: 1 token ≈ 4 ký tự ASCII,
	// tiếng Việt có dấu ≈ 2.5 ký tự/token nên ta dùng 3 cho an toàn).
	charsPerTokenEstimate = 3
)

// tpmLimiters giữ 1 token-bucket dùng chung cho mỗi (provider+model).
// Nhờ vậy 2 instance OpenAILLM trỏ cùng model — hoặc augmenter và contextual
// chia sẻ cùng limiter mà không cần wiring qua tay.
var tpmLimiters = struct {
	m map[string]*rate.Limiter
}{m: map[string]*rate.Limiter{}}

func limiterFor(model string) *rate.Limiter {
	if l, ok := tpmLimiters.m[model]; ok {
		return l
	}
	tpm := defaultOpenAITPM
	if v := os.Getenv("OPENAI_TPM"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			tpm = n
		}
	}
	// Rate = TPM / 60 token/giây; burst = TPM (cho phép gom 1 phút quota
	// vào 1 đợt — khớp đúng cửa sổ tính TPM của OpenAI).
	l := rate.NewLimiter(rate.Limit(float64(tpm)/60.0), tpm)
	tpmLimiters.m[model] = l
	return l
}

type OpenAILLM struct {
	envKey   string
	model    string
	client   *http.Client
	recorder UsageRecorder
	limiter  *rate.Limiter
}

func NewOpenAI(apiKey, model string) *OpenAILLM {
	if model == "" {
		model = "gpt-4o-mini"
	}
	if apiKey != "" {
		os.Setenv("OPENAI_API_KEY", apiKey)
	}
	return &OpenAILLM{
		envKey:  "OPENAI_API_KEY",
		model:   model,
		client:  &http.Client{Timeout: 30 * time.Second},
		limiter: limiterFor(model),
	}
}

// estimateTokens ước lượng token đầu vào + đầu ra cho 1 request.
// Cộng max_tokens vì OpenAI tính cả phần output vào TPM.
func estimateTokens(prompt string) int {
	in := len(prompt)/charsPerTokenEstimate + 1
	return in + openAIMaxTokens
}

func (o *OpenAILLM) SetUsageRecorder(r UsageRecorder) { o.recorder = r }

func (o *OpenAILLM) Name() string { return "openai/" + o.model }

func (o *OpenAILLM) getKey() string { return os.Getenv(o.envKey) }

func (o *OpenAILLM) Generate(ctx context.Context, prompt string) (string, error) {
	start := time.Now()
	key := o.getKey()
	if key == "" {
		o.report(ctx, 0, 0, 0, time.Since(start), fmt.Errorf("api key not configured"))
		return "", fmt.Errorf("openai: API key not configured")
	}
	body := map[string]interface{}{
		"model": o.model,
		"messages": []map[string]interface{}{
			{"role": "user", "content": prompt},
		},
		"temperature": 0.3,
		"max_tokens":  2048,
	}

	jsonBody, _ := json.Marshal(body)

	// Token-bucket: chặn trước khi đụng trần TPM. Ước lượng = prompt/3 + 2048
	// (max_tokens). Sau khi có usage thật ở dưới, ta sẽ reconcile phần chênh.
	estTokens := estimateTokens(prompt)
	if o.limiter != nil {
		burst := o.limiter.Burst()
		if estTokens > burst {
			// 1 request không thể to hơn cả burst — clip để WaitN không lỗi.
			estTokens = burst
		}
		waitStart := time.Now()
		if err := o.limiter.WaitN(ctx, estTokens); err != nil {
			o.report(ctx, 0, 0, 0, time.Since(start), err)
			return "", fmt.Errorf("openai: rate limiter wait: %w", err)
		}
		if waited := time.Since(waitStart); waited > 200*time.Millisecond {
			slog.Debug("openai: throttled by token bucket",
				"model", o.model, "est_tokens", estTokens, "waited_ms", waited.Milliseconds())
		}
	}

	req, err := http.NewRequestWithContext(ctx, "POST", "https://api.openai.com/v1/chat/completions", bytes.NewReader(jsonBody))
	if err != nil {
		o.report(ctx, 0, 0, 0, time.Since(start), err)
		return "", fmt.Errorf("openai: create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+key)

	var (
		resp     *http.Response
		respBody []byte
	)
	for attempt := 0; ; attempt++ {
		// Mỗi lần retry phải clone request vì body đã bị Do() đọc hết.
		reqClone := req.Clone(ctx)
		reqClone.Body = io.NopCloser(bytes.NewReader(jsonBody))

		var doErr error
		resp, doErr = o.client.Do(reqClone)
		if doErr != nil {
			o.report(ctx, 0, 0, 0, time.Since(start), doErr)
			return "", fmt.Errorf("openai: send request: %w", doErr)
		}
		respBody, _ = io.ReadAll(resp.Body)
		resp.Body.Close()

		if resp.StatusCode != 429 || attempt >= maxRateLimitRetries {
			break
		}
		wait := parseRetryAfter(resp.Header, respBody)
		if wait <= 0 {
			// Backoff theo cấp số nhân + jitter nhẹ: 500ms, 1s, 2s, 4s, 8s.
			wait = time.Duration(500*(1<<attempt)) * time.Millisecond
		}
		if wait > maxRateLimitBackoff {
			wait = maxRateLimitBackoff
		}
		slog.Warn("openai: 429 rate limit, retrying",
			"attempt", attempt+1, "max", maxRateLimitRetries, "wait_ms", wait.Milliseconds())
		select {
		case <-ctx.Done():
			o.report(ctx, 0, 0, 0, time.Since(start), ctx.Err())
			return "", fmt.Errorf("openai: context cancelled while waiting for rate limit: %w", ctx.Err())
		case <-time.After(wait):
		}
	}

	if resp.StatusCode != 200 {
		err := fmt.Errorf("openai: API error %d: %s", resp.StatusCode, string(respBody))
		o.report(ctx, 0, 0, 0, time.Since(start), err)
		return "", err
	}

	var result struct {
		Choices []struct {
			Message struct {
				Content string `json:"content"`
			} `json:"message"`
		} `json:"choices"`
		Usage struct {
			PromptTokens     int `json:"prompt_tokens"`
			CompletionTokens int `json:"completion_tokens"`
			TotalTokens      int `json:"total_tokens"`
		} `json:"usage"`
	}
	if err := json.Unmarshal(respBody, &result); err != nil {
		o.report(ctx, 0, 0, 0, time.Since(start), err)
		return "", fmt.Errorf("openai: unmarshal: %w", err)
	}

	if len(result.Choices) == 0 {
		err := fmt.Errorf("openai: empty response")
		o.report(ctx, result.Usage.PromptTokens, result.Usage.CompletionTokens, result.Usage.TotalTokens, time.Since(start), err)
		return "", err
	}

	// Reconcile: nếu usage thật cao hơn ước lượng, tiêu thêm phần chênh khỏi
	// bucket để các request sau bị chặn đúng mức. Nếu thấp hơn, không hoàn —
	// hoàn quota làm bucket chạy quá rate, dễ vượt TPM khi burst.
	if o.limiter != nil && result.Usage.TotalTokens > estTokens {
		diff := result.Usage.TotalTokens - estTokens
		// ReserveN có thể trả delay > 0; ta không Wait, chỉ trừ quota.
		o.limiter.ReserveN(time.Now(), diff)
	}

	o.report(ctx,
		result.Usage.PromptTokens,
		result.Usage.CompletionTokens,
		result.Usage.TotalTokens,
		time.Since(start), nil)

	return result.Choices[0].Message.Content, nil
}

func (o *OpenAILLM) report(ctx context.Context, prompt, output, total int, dur time.Duration, callErr error) {
	if o.recorder == nil {
		return
	}
	uid, uname, hid, src := metaFromCtx(ctx)
	if src == "" {
		src = "llm_chat"
	}
	rec := UsageRecord{
		Provider:     "openai",
		Model:        o.model,
		Operation:    "chat",
		SourceModule: src,
		UserID:       uid,
		UserName:     uname,
		HubID:        hid,
		RequestCount: 1,
		PromptTokens: prompt,
		OutputTokens: output,
		TotalTokens:  total,
		LatencyMs:    int(dur.Milliseconds()),
		Status:       "success",
	}
	if callErr != nil {
		rec.Status = "error"
		rec.ErrorMessage = callErr.Error()
	}
	o.recorder.RecordUsage(rec)
}

// parseRetryAfter trích thời gian chờ từ response 429 của OpenAI.
// Ưu tiên: header Retry-After (giây) → x-ratelimit-reset-tokens (vd "315ms",
// "1.2s") → cụm "try again in Xms" trong body. Trả 0 nếu không bóc được.
func parseRetryAfter(h http.Header, body []byte) time.Duration {
	if v := h.Get("Retry-After"); v != "" {
		if secs, err := strconv.ParseFloat(v, 64); err == nil && secs > 0 {
			return time.Duration(secs * float64(time.Second))
		}
	}
	for _, k := range []string{"x-ratelimit-reset-tokens", "x-ratelimit-reset-requests"} {
		if d := parseDurationLoose(h.Get(k)); d > 0 {
			return d
		}
	}
	if m := reTryAgainIn.FindStringSubmatch(string(body)); len(m) == 3 {
		n, err := strconv.ParseFloat(m[1], 64)
		if err != nil {
			return 0
		}
		if strings.EqualFold(m[2], "ms") {
			return time.Duration(n * float64(time.Millisecond))
		}
		return time.Duration(n * float64(time.Second))
	}
	return 0
}

// parseDurationLoose hiểu "315ms", "1.2s", "2m" — biến thể OpenAI hay dùng.
func parseDurationLoose(s string) time.Duration {
	s = strings.TrimSpace(s)
	if s == "" {
		return 0
	}
	if d, err := time.ParseDuration(s); err == nil {
		return d
	}
	return 0
}
