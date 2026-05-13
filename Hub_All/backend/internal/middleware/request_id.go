package middleware

import (
	"github.com/gin-gonic/gin"
	"github.com/google/uuid"

	"github.com/medinet/hub-all-backend/internal/pkg/requestid"
)

// RequestID đảm bảo mọi request có header X-Request-Id (auto-gen UUID v4
// nếu thiếu) và lưu vào Gin context dưới key requestid.Key. Cũng echo
// header trở lại response để client/proxy log được.
//
// Đặt sớm trong middleware chain (ngay sau Recovery, trước SecurityHeaders)
// để mọi log/error downstream có request_id. KHÔNG validate format UUID
// của header client gửi — accept as-is (Gateway/proxy có thể inject format
// khác như `traceparent`).
func RequestID() gin.HandlerFunc {
	return func(c *gin.Context) {
		rid := c.GetHeader(requestid.HeaderName)
		if rid == "" {
			rid = uuid.NewString()
		}
		c.Set(requestid.Key, rid)
		c.Header(requestid.HeaderName, rid)
		c.Next()
	}
}
