// Package requestid cung cấp key chuẩn + helper trích xuất request_id
// từ Gin context hoặc context.Context — dùng cho cross-service tracing
// (Go ↔ docling-pipeline qua header X-Request-Id).
package requestid

import (
	"context"

	"github.com/gin-gonic/gin"
)

// Key là khóa được middleware.RequestID lưu vào Gin context.
// Cũng dùng làm context.Value key (kiểu string đơn giản — không cần
// custom type vì chỉ middleware này set vào Gin context).
const Key = "request_id"

// HeaderName là tên HTTP header dùng cross-service.
const HeaderName = "X-Request-Id"

// ctxKey là kiểu private dùng làm context.Value key cho With/From
// để tránh collision khi propagate qua context.Context thuần (worker pool).
type ctxKey struct{}

// From trả request_id từ ctx. Hỗ trợ cả `*gin.Context` và `context.Context`
// thuần (vì pipeline.go truyền xuống worker là context.Context, cần fallback
// qua ctxKey{} hoặc string Key). Trả "" nếu không có.
func From(ctx context.Context) string {
	if ctx == nil {
		return ""
	}
	if c, ok := ctx.(*gin.Context); ok {
		if v, exists := c.Get(Key); exists {
			if s, ok := v.(string); ok {
				return s
			}
		}
		return ""
	}
	if v, ok := ctx.Value(ctxKey{}).(string); ok && v != "" {
		return v
	}
	if v, ok := ctx.Value(Key).(string); ok {
		return v
	}
	return ""
}

// With gắn request_id vào context.Context (dùng khi worker nhận job
// từ queue và muốn propagate xuống pipeline / HTTP client).
func With(ctx context.Context, rid string) context.Context {
	return context.WithValue(ctx, ctxKey{}, rid)
}
