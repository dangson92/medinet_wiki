# Medinet Wiki — v3.1 Phase 5: Document Version History

## What This Is

Medinet Wiki là hệ thống quản lý tài liệu nội bộ đa-hub cho Medinet Group, cho phép mỗi hub y tế (dmd, tdt, …) lưu trữ, tra cứu và khai thác tài liệu qua RAG (pgvector + OpenAI embeddings). Phase 5 bổ sung lịch sử phiên bản tài liệu — snapshot tự động mỗi khi tài liệu được reupload/edit/reextract/restore — để đáp ứng yêu cầu audit trail và khả năng rollback của hub_admin.

## Core Value

Người dùng có thể xem lại và khôi phục bất kỳ phiên bản nào của tài liệu trong phạm vi hub họ có quyền — không mất dữ liệu dù reupload nhầm.

## Requirements

### Validated

- ✓ Multi-hub isolation với slug/subpath routing — v3.0
- ✓ RBAC 4-role: admin (super) / hub_admin / editor / viewer với per-hub override — v3.1 Phase 1-2
- ✓ Frontend form 3-option role assignment + hub switcher — v3.1 Phase 3
- ✓ Migration smoke E2E testcontainers 4-scenario — v3.1 Phase 4
- ✓ File extraction mở rộng 8 format (PDF/DOCX/XLSX/CSV/PPTX/HTML/JPG/PNG) — post-v3.1 quick
- ✓ Browser preview modal cho DOCX/XLSX/CSV/HTML — post-v3.1 quick

### Active

- [ ] **VER-01** — Alembic migration tạo bảng `document_versions` (document_id FK, version_number, file_path snapshot, extracted_text snapshot, created_by, created_at)
- [ ] **VER-02** — Service layer: snapshot tự động khi reupload / edit metadata / reextract / manual restore
- [ ] **VER-03** — 4 endpoint REST: `GET /versions`, `GET /versions/{id}`, `POST /versions/{id}/restore`, `DELETE /versions/{id}` — scoped theo hub RBAC
- [ ] **VER-04** — Audit trail: mỗi snapshot ghi `actor_role` + `actor_hub_id` vào payload (nhất quán với Phase 2 audit pattern)
- [ ] **VER-05** — Integration test suite: 5 scenario (create→version, reupload→version, restore, delete, RBAC rejection)

### Out of Scope

- Chunks/vector snapshot per version — defer v4.0; dedupe strategy chưa xác định, chi phí storage lớn
- File binary dedupe (content-hash dedup) — defer v4.0; Phase 5 chỉ snapshot đường dẫn, không copy file
- Version diff UI (side-by-side compare) — defer v4.0; Phase 5 chỉ list + restore
- Cross-hub version restore — không bao giờ; vi phạm hub isolation (D-V3-01 LOCKED)
- Giới hạn "3 gốc + 2 gần nhất" retention policy — gray area GA-V3.1-H, cần discuss trước Phase 5 Plan 01

## Context

- **Frontend đã ship UI tab version history** — gây 404 console error; Phase 5 là backend catch-up bắt buộc
- **Pattern audit từ Phase 2** — `actor_role` + `actor_hub_id` phải nhất quán; đừng tạo audit schema mới
- **Stack**: Python 3.12 · FastAPI · SQLAlchemy async · asyncpg · PostgreSQL 16 + pgvector · Redis 7 · React 19 · Vite 6
- **Windows dev workflow**: bash forward-slash, `uvicorn` native, Postgres/Redis trong Docker; tránh `make` dùng `bash`
- **timestamptz param bug**: raw SQL filter ngày phải dùng `$N::text::timestamptz` (không phải `$N::timestamptz`)
- **Alembic trên Windows**: prefix `PYTHONIOENCODING=utf-8` để tránh cp1252 fail với print() tiếng Việt

## Constraints

- **Tech stack**: Không thêm ORM mới hay migration tool — Alembic + SQLAlchemy async là chuẩn dự án
- **RBAC**: Mọi endpoint VER phải qua `assert_hub_admin_for` hoặc hub-scope viewer check — không bypass như Phase 6 internal-auth gap đã xảy ra
- **Storage**: Snapshot Phase 5 chỉ lưu đường dẫn file + extracted_text, không copy binary — tránh disk explosion
- **Compatibility**: Migration phải có introspect guard (kiểm tra column tồn tại trước khi ALTER) — pattern từ Phase 1
- **Test**: Dùng testcontainers + AsyncIO + httpx AsyncClient — không mock database (bài học từ v2.0)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| `user_hubs.role` nullable (NULL = inherit `users.role`) | Tránh migration backfill toàn bộ user_hubs rows | ✓ Good — Phase 1-2 |
| `admin` giữ nguyên = super-admin (không rename) | Đổi tên gãy JWT chain toàn bộ session đang live | ✓ Good — v3.1 |
| Go backend xoá sớm (Phase 8 → trước Phase 1 v3.0) | Giảm complexity, Python FastAPI đủ cho load hiện tại | ✓ Good — TEARDOWN-01 |
| Sub-hub DB riêng + URL subpath (không subdomain) | Subdomain cần wildcard SSL, subpath deploy dễ hơn trên VPS hiện tại | ✓ Good — v3.0 |
| Snapshot chỉ lưu path + text, không copy file binary | Tránh disk explosion; binary dedup là vấn đề v4.0 | — Pending |
| Retention policy "3 gốc + 2 gần nhất" | Gray area GA-V3.1-H — chưa quyết | — Pending |

---
*Last updated: 2026-05-26 after Phase 5 planning added to ROADMAP (commit 59b4842)*
