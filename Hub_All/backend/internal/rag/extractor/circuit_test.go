package extractor

import (
	"errors"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
	"github.com/redis/go-redis/v9"
	"github.com/sony/gobreaker/v2"
)

// newTestCircuit khởi tạo miniredis + DoclingCircuit với threshold + cooldown
// truyền vào. Trả miniredis instance để test assert key/value.
func newTestCircuit(t *testing.T, threshold uint32, cooldown time.Duration) (*DoclingCircuit, *miniredis.Miniredis) {
	t.Helper()
	mr, err := miniredis.Run()
	if err != nil {
		t.Fatalf("miniredis.Run failed: %v", err)
	}
	t.Cleanup(mr.Close)
	rdb := redis.NewClient(&redis.Options{Addr: mr.Addr()})
	t.Cleanup(func() { _ = rdb.Close() })
	c := NewDoclingCircuit(rdb, threshold, cooldown, nil)
	return c, mr
}

func TestDoclingCircuit_Constructor_NotNil(t *testing.T) {
	c, _ := newTestCircuit(t, 3, 5*time.Minute)
	if c == nil {
		t.Fatal("expected non-nil DoclingCircuit")
	}
	if c.State() != gobreaker.StateClosed {
		t.Errorf("initial state want closed, got %s", c.State().String())
	}
}

func TestDoclingCircuit_OpensAfterThresholdFailures(t *testing.T) {
	c, _ := newTestCircuit(t, 3, 5*time.Minute)
	failErr := errors.New("docling boom")

	// 3 lần fail liên tiếp đủ trip circuit.
	for i := 0; i < 3; i++ {
		err := c.Execute(func() error { return failErr })
		if err == nil {
			t.Fatalf("call %d expected error, got nil", i+1)
		}
	}

	// Lần thứ 4: circuit phải open → trả ErrOpenState, closure KHÔNG được gọi.
	called := false
	err := c.Execute(func() error {
		called = true
		return nil
	})
	if !errors.Is(err, gobreaker.ErrOpenState) {
		t.Fatalf("want ErrOpenState, got %v", err)
	}
	if called {
		t.Error("closure must not be invoked when circuit is open")
	}
	if c.State() != gobreaker.StateOpen {
		t.Errorf("state want open, got %s", c.State().String())
	}
}

func TestDoclingCircuit_RedisStateSyncedOnTransition(t *testing.T) {
	c, mr := newTestCircuit(t, 2, 5*time.Minute)
	failErr := errors.New("boom")

	// Trip circuit (2 fails đủ).
	for i := 0; i < 2; i++ {
		_ = c.Execute(func() error { return failErr })
	}

	// gobreaker OnStateChange trigger sync — assert qua miniredis.
	// Vì sync chạy trong callback inline, không cần wait nhưng cho 50ms buffer.
	deadline := time.Now().Add(500 * time.Millisecond)
	var stateVal, changedAtVal string
	for time.Now().Before(deadline) {
		stateVal, _ = mr.Get(redisKeyCircuitState)
		changedAtVal, _ = mr.Get(redisKeyCircuitChangedAt)
		if stateVal != "" && changedAtVal != "" {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}

	if stateVal != "open" {
		t.Errorf("redis state want 'open', got %q", stateVal)
	}
	if changedAtVal == "" {
		t.Errorf("redis changed_at must be set")
	}
}

func TestDoclingCircuit_StateStringEnum(t *testing.T) {
	c, _ := newTestCircuit(t, 3, 5*time.Minute)
	if got := c.State().String(); got != "closed" {
		t.Errorf("initial state String() want 'closed', got %q", got)
	}

	failErr := errors.New("boom")
	for i := 0; i < 3; i++ {
		_ = c.Execute(func() error { return failErr })
	}
	if got := c.State().String(); got != "open" {
		t.Errorf("after threshold String() want 'open', got %q", got)
	}
}

func TestDoclingCircuit_BelowThresholdStaysClosed(t *testing.T) {
	c, _ := newTestCircuit(t, 3, 5*time.Minute)
	failErr := errors.New("boom")

	// 2 lần fail (dưới threshold 3) — circuit phải vẫn closed.
	for i := 0; i < 2; i++ {
		_ = c.Execute(func() error { return failErr })
	}
	if c.State() != gobreaker.StateClosed {
		t.Fatalf("state want closed after 2 fails, got %s", c.State().String())
	}

	// Lần thứ 3 closure VẪN được phép gọi (circuit chưa open).
	called := false
	err := c.Execute(func() error {
		called = true
		return nil
	})
	if err != nil {
		t.Fatalf("3rd call (success) want nil err, got %v", err)
	}
	if !called {
		t.Error("closure must be invoked when circuit is closed")
	}
	// Sau 1 success counts.ConsecutiveFailures reset về 0.
	if got := c.Counts().ConsecutiveFailures; got != 0 {
		t.Errorf("ConsecutiveFailures want 0 after success, got %d", got)
	}
}
