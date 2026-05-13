# Testing Patterns

**Ngày phân tích:** 2026-04-28

## Tóm tắt

> **Trạng thái: CHƯA CÓ TEST.** Codebase Hub_All hiện không có bất kỳ file test nào ở cả backend (`*_test.go`) lẫn frontend (`*.test.*` / `*.spec.*`). Không có framework test nào được cài đặt. Không có cấu hình coverage. Mục này mô tả hiện trạng và đề xuất hướng triển khai test khi bắt đầu.

Lệnh kiểm chứng đã chạy:
- Backend: `find backend -name "*_test.go"` → không có kết quả.
- Frontend: `find frontend/src -name "*.test.*" -o -name "*.spec.*"` → không có kết quả.

---

## 1. Backend (Go)

### Hạ tầng test sẵn sàng

- **Runner mặc định:** Go testing built-in (`go test`) — không cần thêm dependency.
- Mục tiêu Makefile đã chuẩn bị sẵn nhưng **chưa có test để chạy**:
  - `backend/Makefile` dòng 51-52: `test: go test ./... -v -count=1`.
  - `backend/Makefile` dòng 54-56: `test-coverage: go test ./... -coverprofile=coverage.out && go tool cover -html=coverage.out`.

### Test framework hiện có

- **Chưa cài đặt** assertion library (chưa có `testify`, `gomock`, `mockery`, ...).
- `go.mod` (`backend/go.mod`) không liệt kê dependency test nào.

### Vị trí test (đề xuất khi triển khai)

- Theo Go convention: file test nằm cạnh file source, đặt tên `<file>_test.go`.
- Ví dụ:
  - `backend/internal/service/auth_service_test.go` cho `auth_service.go`.
  - `backend/internal/repository/user_repo_test.go` cho `user_repo.go`.
- Package test có thể là cùng package (white-box) hoặc `<package>_test` (black-box).

### Pattern đề xuất

- **Unit test service:** mock repository (interface) — hiện tại các struct `*UserRepo`, `*TokenRepo` là concrete pointer, **chưa có interface để mock**. Khi viết test cần refactor service nhận interface (ví dụ `type UserRepoIface interface { FindByEmail(...) ... }`).
- **Repository test:** dùng Postgres test container (`testcontainers-go`) hoặc DB test riêng theo `DB_NAME=medinet_test`.
- **Handler test:** dùng `httptest.NewRecorder()` + Gin engine, gọi route trực tiếp.
- **JWT/auth test:** cấp keypair test cố định trong fixture, generate token bằng `jwtpkg.Manager`.

### Mocking

- Chưa có pattern mocking. Gợi ý:
  - Dùng `gomock` + interface declaration để generate mock.
  - Hoặc viết stub bằng tay trong từng test package.

### Coverage

- Chưa có baseline. Lệnh `make test-coverage` đã có sẵn để mở report HTML khi đã có test.

---

## 2. Frontend (React + TypeScript)

### Hạ tầng test sẵn sàng

- **Chưa cài đặt** test runner. `frontend/package.json` không có Vitest, Jest, Playwright, Cypress, Testing Library hay Mocha trong `dependencies` / `devDependencies`.
- Script `npm run lint` thực chất chỉ chạy `tsc --noEmit` (type-check), **không phải** lint hay test.
- Không có file `vitest.config.ts`, `jest.config.*`, `playwright.config.*`.

### Đề xuất stack khi bổ sung

- **Unit / component test:** Vitest + `@testing-library/react` + `@testing-library/jest-dom` (Vitest dễ tích hợp với Vite đã có).
- **E2E:** Playwright (khi UI ổn định).

### Vị trí test (đề xuất)

- Co-located cạnh component: `frontend/src/components/Pagination.test.tsx`.
- Hoặc tách thư mục `frontend/src/__tests__/` cho test nhóm theo tính năng.

### Mocking

- Chưa có pattern. Gợi ý khi triển khai:
  - Mock `fetch` toàn cục bằng `vi.fn()` của Vitest hoặc dùng `msw` (Mock Service Worker) để chặn request HTTP.
  - Mock `localStorage` qua `vi.spyOn(Storage.prototype, 'getItem')` để test logic trong `frontend/src/services/api.ts` (token refresh, redirect khi 401).
  - Mock `react-router-dom` qua `MemoryRouter` để test page có `useNavigate`.

### Test Types đáng ưu tiên (đề xuất)

| Loại | Khu vực | Ví dụ kịch bản |
|------|---------|----------------|
| Unit | `frontend/src/lib/utils.ts` | `cn()` merge class đúng, override Tailwind đúng |
| Unit | `frontend/src/services/api.ts` | retry sau refresh token, redirect `/login` khi 401 |
| Component | `frontend/src/components/Pagination.tsx` | render đúng số trang, gọi `onPageChange` |
| Component | `frontend/src/pages/Login.tsx` | hiển thị state `error` / `locked`, đếm ngược countdown |
| Integration | `frontend/src/contexts/AuthContext.tsx` | `login` thành công set state, `logout` xoá token |

---

## 3. Backend smoke binaries (không phải test)

Trong `backend/cmd/` có các binary tiện ích (không phải Go test):
- `backend/cmd/hashpw/` — sinh password hash thủ công.
- `backend/cmd/testpdf/` — kiểm tra parser PDF.
- `backend/cmd/testtoken/` — kiểm tra JWT.

Đây là CLI helpers, **không phải** automated test, không tích hợp `go test`.

---

## 4. Coverage hiện tại

- **Backend:** 0% — không có test.
- **Frontend:** 0% — không có test.
- Không có CI pipeline kiểm tra test (chưa thấy `.github/workflows/`, `gitlab-ci.yml`, `Jenkinsfile`).

---

## 5. Khuyến nghị ưu tiên triển khai

1. **Backend P0:** test cho `backend/internal/pkg/jwt/` và `backend/internal/pkg/hash/` — pure function, dễ test, đảm bảo bảo mật.
2. **Backend P1:** test `auth_service.Login` (lock account sau 5 lần fail, reset failed_login_count, role priority) — nghiệp vụ phức tạp, dễ regression.
3. **Backend P1:** integration test `auth_handler` qua `httptest` để cover happy path login/refresh/logout.
4. **Frontend P0:** thêm Vitest + RTL, bắt đầu với `lib/utils.ts` và `services/api.ts` (logic refresh).
5. **Frontend P1:** component test cho `Pagination`, `Login` (state machine).
6. **CI:** thêm GitHub Action chạy `make test` (backend) và `npm run lint && npm test` (frontend) trên mỗi PR.

---

*Phân tích testing: 2026-04-28*
