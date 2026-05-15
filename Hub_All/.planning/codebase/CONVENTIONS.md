# Coding Conventions

> ⚠️ **STALE — KHÔNG DÙNG LÀM REFERENCE.** Snapshot này phân tích codebase Go cũ (`backend/`) đã xóa khỏi working tree 2026-05-14 (TEARDOWN-01 pull-in). Chỉ giữ làm tư liệu lịch sử. Convention M2 hiện hành: `.planning/CONVENTIONS.md` (Python `api/`). Reference cho Phase 5/6/7: `frontend/src/services/api.ts` + git tag `m1-go-archived`.

**Ngày phân tích:** 2026-04-28

Tài liệu mô tả các quy ước code đang được áp dụng trong codebase Hub_All (`backend/` Go + Gin và `frontend/` React+Vite+TypeScript+Tailwind). Khi thêm code mới, tuân thủ chính xác các pattern bên dưới để giữ tính nhất quán.

## Quy ước theo từng phần

Codebase chia làm hai khu vực có quy ước khác nhau:
- **Backend Go**: `backend/` — dùng style chuẩn của Go (gofmt, idiomatic Go).
- **Frontend TypeScript/React**: `frontend/src/` — dùng style ESM, JSX, Tailwind utility classes.

---

## 1. Backend (Go)

### Naming Patterns

**Packages:**
- Một thư mục = một package, tên thư mục viết thường, không gạch nối: `handler`, `service`, `repository`, `model`, `middleware`.
- Sub-package nhỏ trong `internal/pkg/` cho tiện ích dùng chung: `internal/pkg/response/`, `internal/pkg/jwt/`, `internal/pkg/hash/`, `internal/pkg/crypto/`, `internal/pkg/validator/`.

**Files:**
- Snake_case kèm hậu tố vai trò: `auth_handler.go`, `auth_service.go`, `user_repo.go`, `apikey_repo.go`.
- File model theo entity: `user.go`, `hub.go`, `apikey.go` trong `backend/internal/model/`.
- File migrations đánh số: `001_bootstrap.up.sql` / `001_bootstrap.down.sql` trong `backend/internal/database/migrations/`.

**Identifiers:**
- Exported (public): `PascalCase` — `AuthService`, `LoginRequest`, `NewUserRepo`, `JWTAuth`.
- Unexported (private): `camelCase` — `authService`, `userRepo`, `jwtManager`, `pool`.
- Constants: `PascalCase` cho exported, có thể dùng prefix nhóm: `ContextUserID`, `ContextEmail`, `ContextJTI` (xem `backend/internal/middleware/auth.go`).
- Các kiểu interface ngắn gọn, tên kết thúc bằng `-er` khi mô tả hành vi (theo Go idiom).

**Struct fields với JSON tag:**
- Field Go là `PascalCase`, JSON tag là `snake_case`.
- Ví dụ trong `backend/internal/model/user.go`:
  ```go
  type User struct {
      ID               uuid.UUID  `json:"id"`
      Email            string     `json:"email"`
      PasswordHash     string     `json:"-"` // never expose
      FailedLoginCount int        `json:"failed_login_count"`
      LockedUntil      *time.Time `json:"locked_until,omitempty"`
  }
  ```
- Trường nhạy cảm dùng tag `json:"-"` để không bao giờ serialize.
- Trường nullable dùng `*string`, `*time.Time` kèm `omitempty`.

### Module Structure (Layered)

Mỗi feature theo layer:
1. **Handler** (`backend/internal/handler/*.go`) — bind request, gọi service, trả response.
2. **Service** (`backend/internal/service/*.go`) — business logic, gọi repo.
3. **Repository** (`backend/internal/repository/*.go`) — query Postgres bằng `pgx`, không chứa logic nghiệp vụ.
4. **Model** (`backend/internal/model/*.go`) — struct dữ liệu, request/response DTO.

Constructor pattern bắt buộc: `NewXxx(...) *Xxx`.
Ví dụ `backend/internal/service/auth_service.go`:
```go
func NewAuthService(userRepo *repository.UserRepo, tokenRepo *repository.TokenRepo, ...) *AuthService {
    return &AuthService{userRepo: userRepo, tokenRepo: tokenRepo, ...}
}
```

### Code Style

**Formatting:**
- Dùng `gofmt` mặc định (tab indent, dấu ngoặc cùng dòng).
- Chưa có file cấu hình `.golangci.yml` ở repo (lệnh `make lint` trong `backend/Makefile` gọi `golangci-lint run ./...` nhưng config nằm ngoài repo hoặc theo default).

**Linting:**
- Mục tiêu `lint` trong `backend/Makefile`: `golangci-lint run ./...` — chưa có file cấu hình riêng, chạy theo preset mặc định.

**Imports:**
- Chia 3 nhóm, cách nhau bằng dòng trống, theo gofmt:
  1. Standard library (`context`, `fmt`, `log/slog`, `time`).
  2. Third-party (`github.com/gin-gonic/gin`, `github.com/google/uuid`, `github.com/jackc/pgx/v5`).
  3. Internal (`github.com/medinet/hub-all-backend/internal/...`).
- Alias khi tên trùng: `jwtpkg "github.com/medinet/hub-all-backend/internal/pkg/jwt"` (xem `backend/internal/handler/auth_handler.go`, `backend/internal/middleware/auth.go`).

### Error Handling

**Wrapping lỗi:**
- Mọi lỗi từ tầng dưới được wrap bằng `fmt.Errorf("context: %w", err)` để giữ chain.
- Ví dụ trong `backend/internal/repository/user_repo.go`:
  ```go
  if err != nil {
      return nil, fmt.Errorf("find user by email: %w", err)
  }
  ```

**Phân biệt "không tìm thấy" vs lỗi:**
- Repo trả `(nil, nil)` khi `pgx.ErrNoRows`, lỗi thật mới wrap:
  ```go
  if err == pgx.ErrNoRows { return nil, nil }
  if err != nil { return nil, fmt.Errorf("...: %w", err) }
  ```

**Trả lỗi ra HTTP:**
- Handler dùng helper trong `backend/internal/pkg/response/response.go`:
  - `response.OK(c, data)` — 200.
  - `response.Created(c, data)` — 201.
  - `response.Paginated(c, data, meta)` — 200 + meta phân trang.
  - `response.BadRequest(c, msg)` / `Unauthorized` / `Forbidden` / `NotFound` / `Conflict` / `TooManyRequests` / `InternalError`.
- Mọi response đều theo schema `{success, data?, error?, meta?}` với `error: {code, message}`.
- Code lỗi viết HOA gạch dưới: `BAD_REQUEST`, `UNAUTHORIZED`, `RATE_LIMIT_EXCEEDED`, `INTERNAL_ERROR`.

### Logging

**Framework:** `log/slog` (chuẩn thư viện Go).

**Pattern:**
- Key-value structured: `slog.Debug("login failed", "email", req.Email, "error", err)`.
- Cấp độ:
  - `slog.Debug` — chi tiết lỗi nghiệp vụ (sai mật khẩu, token sai).
  - `slog.Error` — lỗi hệ thống không mong đợi (DB fail, Redis fail).
- Không log password, token đầy đủ; mask khi cần (xem `maskKey` trong `backend/internal/router/router.go`).

### Handler Pattern

Mỗi handler method theo skeleton (xem `backend/internal/handler/auth_handler.go`):
```go
func (h *AuthHandler) Login(c *gin.Context) {
    var req model.LoginRequest
    if err := c.ShouldBindJSON(&req); err != nil {
        response.BadRequest(c, "invalid request body")
        return
    }
    result, err := h.authService.Login(c.Request.Context(), req)
    if err != nil {
        slog.Debug("login failed", "email", req.Email, "error", err)
        response.Unauthorized(c, err.Error())
        return
    }
    response.OK(c, result)
}
```
Quy tắc:
- Luôn dùng `c.ShouldBindJSON` để bind + validate (kết hợp tag `binding:"required"` trong model).
- Truyền `c.Request.Context()` xuống service.
- Lấy giá trị middleware bằng `c.Get(string(middleware.ContextUserID))`, ép kiểu `(string)` rồi dùng.
- Thoát sớm sau mỗi `response.Xxx(...)` bằng `return`.

### Repository Pattern

- Field duy nhất: `pool *pgxpool.Pool`.
- Mọi method nhận `ctx context.Context` đầu tiên.
- Query SQL viết multi-line raw string với backtick:
  ```go
  err := r.pool.QueryRow(ctx, `
      SELECT id, email, name, ...
      FROM users WHERE email = $1
  `, email).Scan(&u.ID, &u.Email, &u.Name, ...)
  ```
- Dùng `$1, $2, ...` (placeholder Postgres), không dùng string concatenation.
- List/filter động: build `conditions []string` + `args []interface{}` + `argIdx`, join bằng `" AND "` (xem `ListUsers` trong `backend/internal/repository/user_repo.go`).

### Validation

- Tag `binding:"required"` trên struct request (xem `LoginRequest`, `RefreshRequest` trong `backend/internal/model/user.go`).
- Validation phức tạp đặt trong `backend/internal/pkg/validator/`.

### Function Design

- Constructor `NewXxx` ngắn, chỉ gán field.
- Service method luôn `(ctx context.Context, ...)` đầu tiên, trả `(*Result, error)` hoặc `error`.
- Handler không trả gì (gọi `response.Xxx(c, ...)` trực tiếp).

---

## 2. Frontend (TypeScript + React)

### TypeScript Config

- File: `frontend/tsconfig.json`.
- `target: ES2022`, `module: ESNext`, `moduleResolution: bundler`.
- `jsx: react-jsx` (không cần `import React` cho JSX, nhưng các file hiện có vẫn import — không bắt buộc bỏ).
- `noEmit: true` — TypeScript chỉ làm type-check, build do Vite.
- Path alias: `"@/*": ["./*"]` — chỉ về root `frontend/`. Tuy nhiên codebase chủ yếu dùng đường dẫn tương đối (`../contexts/AuthContext`, `../services/api`).
- Lệnh kiểm tra: `npm run lint` thực ra chạy `tsc --noEmit` (xem `frontend/package.json`). **Không có ESLint, không có Prettier, không có Biome.**

### Naming Patterns

**Files:**
- Component và page: `PascalCase.tsx` — `Login.tsx`, `Dashboard.tsx`, `Pagination.tsx`, `RichTextEditor.tsx`, `GeminiAssistant.tsx`, `CitationText.tsx`.
- Context: `XxxContext.tsx` — `AuthContext.tsx`, `ThemeContext.tsx` trong `frontend/src/contexts/`.
- Tiện ích / service: `camelCase.ts` — `frontend/src/services/api.ts`, `frontend/src/lib/utils.ts`, `frontend/src/types.ts`, `frontend/src/mockData.ts`.

**Identifiers:**
- Component, type, interface: `PascalCase` — `LoginPage`, `AuthProvider`, `Hub`, `User`, `LoginState`.
- Hook: `useXxx` — `useAuth`, `useNavigate`, `useState`, `useEffect`, `useCallback`.
- Biến, hàm thường: `camelCase` — `handleSubmit`, `formatTime`, `mapHubAPIToHub`, `accessToken`.
- Constant cấp module: `UPPER_SNAKE_CASE` — `API_URL` trong `frontend/src/services/api.ts`.

**JSON từ backend → TypeScript:**
- Trường BE là `snake_case` (`access_token`, `hub_id`), giữ nguyên trong type API (`HubAPI`, `LoginResponse` trong `frontend/src/services/api.ts`).
- Type frontend nội bộ dùng `camelCase` (`hubId`, `lastUpdate`, `pendingSync` trong `frontend/src/types.ts`).
- Khi nhận data từ BE thì map sang shape FE qua hàm `mapXxxAPIToXxx` (xem `mapHubAPIToHub`, `mapAuditLogToFE` trong `frontend/src/pages/Dashboard.tsx`).

### Component Structure

Page component theo skeleton (xem `frontend/src/pages/Login.tsx`):
```tsx
import React, { useState, useEffect } from 'react';
import { Mail, Lock } from 'lucide-react';
import { motion } from 'motion/react';
import { useAuth } from '../contexts/AuthContext';

type LoginState = 'default' | 'loading' | 'error' | 'locked';

const LoginPage = () => {
  const [state, setState] = useState<LoginState>('default');
  // ...
  const handleSubmit = async (e: React.FormEvent) => { ... };
  return ( <div>...</div> );
};

export default LoginPage;
```

Quy tắc:
- Một component / một file `.tsx`, export default cho page và component lớn (xem `Pagination.tsx`).
- Có thể dùng `function ComponentName(...)` hoặc `const ComponentName = () => {...}` — cả hai đều xuất hiện, chọn theo file hiện có khi sửa.
- Khai báo `type LoginState = '...' | '...'` ngay đầu file cho local state machine.
- State đặt cùng nhau bằng `useState` (ví dụ `Login.tsx` có 5 `useState`); nếu state liên quan, gom thành object như `AuthContext.tsx` (`AuthState`).
- Side effect dùng `useEffect`; cleanup trả function (`return () => clearInterval(timer);`).

### State Management

- **Global state:** Context API, không có Redux/Zustand. Provider trong `frontend/src/contexts/`:
  - `AuthContext.tsx` — quản lý `user`, `isAuthenticated`, `isLoading` + `login/logout/refreshUser`.
  - `ThemeContext.tsx` — theme.
- Pattern hook gắn với context (xem `AuthContext.tsx`):
  ```ts
  export function useAuth() {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error('useAuth must be used within AuthProvider');
    return ctx;
  }
  ```
- **Local state:** `useState` trong component.
- **Server state:** chưa dùng React Query / SWR — gọi `api.xxx()` trong `useEffect` rồi set state thủ công.

### API Client

- Tập trung trong `frontend/src/services/api.ts` qua class `APIClient` với method `request<T>(method, path, body?)`.
- Token JWT lưu `localStorage` (`access_token`, `refresh_token`).
- Tự động retry sau khi refresh token (`tryRefresh`); 401 sau refresh fail → xóa token, `window.location.href = '/login'`.
- Mọi method API đặt theo nhóm có comment phân nhóm (`// ─── Auth ───`, `// ─── Hubs ───`).
- Response chuẩn hóa interface `APIResponse<T>` khớp với backend `response.APIResponse`.

### Error Handling (UI)

- Catch trong component, set state `errorMessage`, render conditionally.
- Login dùng state machine `'default' | 'loading' | 'error' | 'locked'` để điều khiển UI.
- Lỗi network: `err instanceof Error ? err.message : 'Network error'`.
- Thông báo lỗi cho người dùng viết bằng tiếng Việt: `'Đăng nhập thất bại'`, `'phút'`.

### Styling

- **Tailwind CSS v4** qua `@tailwindcss/vite` — không có `tailwind.config.js` riêng (cấu hình inline trong CSS qua Tailwind v4).
- Class viết trực tiếp trên JSX, dùng `cn(...)` (`clsx` + `tailwind-merge`) khi cần điều kiện:
  ```ts
  // frontend/src/lib/utils.ts
  export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
  }
  ```
- Animation: `motion/react` (`<motion.div>`, `AnimatePresence`).
- Icon: `lucide-react`.

### Imports

**Thứ tự (quan sát từ các file):**
1. React và hook (`import React, { useState } from 'react'`).
2. Third-party (`lucide-react`, `motion/react`, `react-router-dom`, `@tiptap/*`).
3. Internal: contexts → services → lib → types → components.
4. CSS / asset (nếu có).

**Style:**
- ES module, dùng single-quote `'...'`, có dấu chấm phẩy cuối câu.
- `import type { ... }` cho type-only import (xem `import type { ReactNode }` trong `AuthContext.tsx`, `import type { Hub, AuditLogEntry } from '../types'` trong `Dashboard.tsx`).
- Đường dẫn tương đối; alias `@/` đã định nghĩa nhưng ít dùng.

### Comments

- Comment ngắn dùng `//`, ngôn ngữ tiếng Anh hoặc tiếng Việt tùy file.
- Phân vùng code trong file lớn bằng banner `/* ── Tên vùng ── */` (xem `Dashboard.tsx`).
- Không dùng JSDoc/TSDoc rộng rãi.

### Function Design

- Handler trong component đặt tên `handleXxx` (`handleSubmit`, `handleSelect`).
- Map function: `mapXxxAPIToXxx` cho biến đổi BE→FE.
- Hook tự viết: tên `useXxx`.

### Module Design

- Không dùng barrel `index.ts` cho thư mục — import trực tiếp file.
- Mỗi page là một file độc lập trong `frontend/src/pages/`.
- Component dùng chung trong `frontend/src/components/`.

---

## 3. SQL Migrations

- Vị trí: `backend/internal/database/migrations/`.
- Tool: `golang-migrate/migrate`.
- Đặt tên: `NNN_short_name.up.sql` + `NNN_short_name.down.sql` (3 chữ số đầu).
- Đã có 8 cặp migration (`001_bootstrap` → `008_usage_rollup`).

---

## 4. Tóm tắt nhanh "Khi viết code mới"

| Tác vụ | Vị trí | Tham khảo file |
|--------|--------|---------------|
| Thêm endpoint mới | `backend/internal/handler/<feature>_handler.go` + `service` + `repository` | `auth_handler.go` |
| Thêm bảng DB | Tạo migration `NNN_xxx.up.sql` + `.down.sql` | `001_bootstrap.up.sql` |
| Thêm trang FE | `frontend/src/pages/<Name>.tsx` + thêm route trong `frontend/src/App.tsx` | `Dashboard.tsx`, `Login.tsx` |
| Thêm component FE | `frontend/src/components/<Name>.tsx` | `Pagination.tsx` |
| Thêm method API | Bổ sung vào class `APIClient` trong `frontend/src/services/api.ts` | `api.ts` |
| Thêm context | `frontend/src/contexts/<Name>Context.tsx` + provider + hook | `AuthContext.tsx` |
| Thêm type chung FE | `frontend/src/types.ts` (cho dùng chung) hoặc khai báo trong file | `types.ts` |
| Trả response BE | Dùng `response.OK / BadRequest / Unauthorized / ...` | `pkg/response/response.go` |

---

*Phân tích quy ước: 2026-04-28*
