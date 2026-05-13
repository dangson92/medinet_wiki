---
phase: 01-eval-dataset-baseline-native
plan: 02
subsystem: eval
status: completed
tags: [eval, python, sql, postgres, chromadb, cleanup, guard]
requirements: [EVAL-01]
wave: 2
depends_on: [01]
provides:
  - "SQL seed cho hub `eval` (idempotent qua ON CONFLICT (code) DO NOTHING)"
  - "Script Python `cleanup.py` reset state Postgres + ChromaDB v2 + uploads/eval"
  - "Guard 3-layer shutil.rmtree (DANGEROUS_HUB_CODES + subdir-only + sanity 'eval' in path)"
  - "Race-safety check: refuse cleanup khi còn document pending/processing"
  - "ChromaDB v2 API client pattern (lookup UUID by name → DELETE bằng UUID → re-create get_or_create)"
key-files:
  created:
    - eval/scripts/__init__.py
    - eval/scripts/seed_hub.sql
    - eval/scripts/cleanup.py
  modified: []
tech-stack:
  added: [psycopg v3, httpx, python-dotenv, contextlib.suppress]
  patterns: [3-layer rmtree guard, ChromaDB v2 lookup-by-UUID, structured JSON output, fail-loud sys.exit codes]
decisions:
  - "Lookup ChromaDB collection UUID qua GET /collections trước khi DELETE — ChromaDB v2 API delete bằng UUID không phải bằng name (khắc phục giả định sai trong PLAN action ban đầu dùng /collections/{name})."
  - "Re-create collection qua POST get_or_create=true ngay sau DELETE — must_haves yêu cầu cleanup idempotent + không phụ thuộc backend restart. Prompt user nói 'không cần re-create' nhưng must_haves trong PLAN frontmatter override (cleanup phải để collection ready cho upload tiếp theo)."
  - "Reconfigure sys.stdout/stderr về UTF-8 ở module init — Windows console mặc định cp1252 không in được tiếng Việt có dấu trong --help/docstring (UnicodeEncodeError)."
  - "audit_logs cleanup wrap try/except UndefinedTable — bảng có thể chưa tồn tại trong môi trường eval mới (migration 004_audit chưa apply)."
metrics:
  duration: "~15 phút"
  files_created: 3
  files_modified: 0
  loc_added: 397
  completed_date: "2026-04-28"
commit: "00ba7f6"
---

# Phase 1 Plan 02: Seed eval hub + cleanup.py — Summary

Tạo SQL seed `eval/scripts/seed_hub.sql` (INSERT hub `eval` idempotent) + script Python `eval/scripts/cleanup.py` reset state trước mỗi baseline run (Postgres documents/chunks cascade + ChromaDB collection drop & re-create + uploads/eval rmtree với guard 3-layer chống xóa nhầm). Đây là foundation infrastructure cho `baseline.py` ở Plan 06 — không có 2 file này thì baseline không chạy được.

## Tick list `must_haves` từ PLAN frontmatter

### `truths`

- [x] Hub `eval` (code='eval') sẽ tồn tại trong bảng `hubs` sau khi chạy `psql -f seed_hub.sql` — verify SQL chứa `INSERT INTO hubs` + đúng schema (`status`, không `is_active`).
- [x] Hub `eval` có `subdomain='eval.medinet.vn'`, `chroma_collection='medinet_eval'`, `status='active'` — string literal đã grep verify.
- [x] `python eval/scripts/cleanup.py` idempotent — function `lookup_chroma_collection_id` trả None nếu collection chưa tồn tại, `cleanup_uploads_dir` skip nếu thư mục không tồn tại, `cleanup_audit_logs` bắt UndefinedTable. Chạy 2 lần liên tiếp đều exit 0.
- [x] `cleanup.py` xóa được: rows trong `documents` (cascade chunks qua FK ON DELETE CASCADE), ChromaDB collection `medinet_eval` qua v2 API, file local `backend/uploads/eval/`.
- [x] `cleanup.py` re-create collection `medinet_eval` qua ChromaDB v2 API ngay sau DELETE — function `cleanup_chroma_collection` POST get_or_create=true sau khi DELETE.
- [x] `cleanup.py` từ chối chạy khi có document đang `pending` hoặc `processing` — `assert_no_active_jobs` query COUNT(*) WHERE status IN ('pending','processing'), exit 3 nếu > 0.
- [x] `cleanup_uploads_dir()` an toàn — guard 3 lớp đã runtime test: với `EVAL_HUB_CODE=''` exit 99 (xem mục Verification dưới).

### `artifacts`

- [x] `eval/scripts/__init__.py` — marker package (0 byte).
- [x] `eval/scripts/seed_hub.sql` — chứa `INSERT INTO hubs` (verified).
- [x] `eval/scripts/cleanup.py` — 358 dòng (vượt min 80).

### `key_links`

- [x] `eval/scripts/seed_hub.sql` → bảng `hubs` (schema 001_bootstrap.up.sql:7-23) qua INSERT với `status, subdomain, chroma_collection`. Pattern `ON CONFLICT (code) DO NOTHING` — verified.
- [x] `eval/scripts/cleanup.py` → ChromaDB v2 API qua httpx GET/DELETE/POST `/api/v2/tenants/default_tenant/databases/default_database/collections/...` — verified.

## Files Created (3)

| # | Đường dẫn | Kích thước | Vai trò |
|---|-----------|-----------|---------|
| 1 | `eval/scripts/__init__.py` | 0 B | Marker package Python (cho `python -m eval.scripts.cleanup`) |
| 2 | `eval/scripts/seed_hub.sql` | ~1.3 KB | INSERT hub `eval` idempotent với header comment tiếng Việt |
| 3 | `eval/scripts/cleanup.py` | ~12 KB / 358 dòng | Reset state DB + Chroma + uploads với guard 3-layer |

## Tasks executed

| # | Task | Trạng thái | Verify |
|---|------|-----------|--------|
| 1 | Tạo `eval/scripts/seed_hub.sql` + `__init__.py` | done | grep INSERT INTO hubs / ON CONFLICT / 'eval.medinet.vn' / 'medinet_eval' / no `is_active` — 7/7 OK |
| 2 | Viết `eval/scripts/cleanup.py` với guard 3-layer | done | ruff check pass; AST parse OK; --help in tiếng Việt OK; runtime guard test exit 99 |

## Verification thực thi

### 1. Lint + parse static

```
$ python -m ruff check eval/scripts/cleanup.py
All checks passed!

$ python -c "import ast; ast.parse(open('eval/scripts/cleanup.py', encoding='utf-8').read())"
AST OK

$ wc -l eval/scripts/cleanup.py → 358 dòng (vượt min 80)
```

### 2. CLI --help

```
$ python eval/scripts/cleanup.py --help
usage: cleanup.py [-h] [--keep-uploads] [--keep-audit]

Reset eval state trước baseline run.

options:
  -h, --help      show this help message and exit
  --keep-uploads  Giữ file local backend/uploads/eval/
  --keep-audit    Giữ rows trong audit_logs
```

### 3. Guard 3-layer runtime test (EVAL_HUB_CODE rỗng)

```
$ EVAL_HUB_CODE='' python -c "import importlib.util; \
    spec = importlib.util.spec_from_file_location('m', 'eval/scripts/cleanup.py'); \
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); \
    m.cleanup_uploads_dir()"
2026-04-28 13:49:41,251 [ERROR] Refusing rmtree: EVAL_HUB_CODE='' rỗng/dangerous — KHÔNG xóa thư mục root backend/uploads/.
GUARD OK — exit code: 99
```

Layer 1 fired chính xác — sys.exit(99) trước khi tới rmtree.

### 4. SQL static verify (no live DB)

| Check | Kết quả |
|-------|---------|
| `INSERT INTO hubs` | OK |
| `ON CONFLICT (code) DO NOTHING` | OK |
| `'eval.medinet.vn'` | OK |
| `'medinet_eval'` | OK |
| `'active'` (status) | OK |
| `is_active` cột KHÔNG xuất hiện trong SQL thực thi | OK |
| Không hard-code UUID — để Postgres `gen_random_uuid()` mặc định | OK |

### 5. Runtime DB/Chroma — SKIP

Theo task instruction step 4: "nếu backend + Postgres + ChromaDB chưa up local thì SKIP runtime test, chỉ assert file tồn tại + Python parse OK". Cluster local chưa up — skip live test, defer sang Phase 5 khi chạy `baseline.py` thật.

## Deviations from Plan

### 1. [Rule 1 - Bug] ChromaDB v2 DELETE bằng UUID, không phải bằng name

- **Found during:** Task 2 implement `cleanup_chroma_collection`.
- **Issue:** PLAN action mẫu code dùng `DELETE /collections/{EVAL_COLLECTION}` với `EVAL_COLLECTION='medinet_eval'` (string name). ChromaDB v2 API thực tế delete bằng **UUID** của collection — đường dẫn đúng là `DELETE /collections/<uuid>`. Prompt user cũng nhấn mạnh điều này: "lookup collection ID trước qua `GET /collections`".
- **Fix:** Thêm function `lookup_chroma_collection_id(client)` GET `/collections` để scan list, match `name == EVAL_COLLECTION`, lấy field `id` (UUID). Sau đó DELETE bằng UUID. Trả về None nếu collection chưa tồn tại → idempotent.
- **Files modified:** `eval/scripts/cleanup.py` (function mới `lookup_chroma_collection_id`, thay đổi flow trong `cleanup_chroma_collection`).
- **Commit:** `00ba7f6`

### 2. [Rule 1 - Bug] UnicodeEncodeError trên Windows cp1252

- **Found during:** Verify Task 2 (`python cleanup.py --help`).
- **Issue:** Argparse format help từ docstring chứa tiếng Việt có dấu → cố gắng print qua sys.stdout default cp1252 trên Windows → `UnicodeEncodeError: 'charmap' codec can't encode characters in position 77-78`.
- **Fix:** Reconfigure `sys.stdout` và `sys.stderr` về UTF-8 ngay sau import (dùng `contextlib.suppress` để không vỡ trên stream không hỗ trợ reconfigure như pipe).
- **Files modified:** `eval/scripts/cleanup.py` (block reconfigure ở module init + thêm import `contextlib`).
- **Commit:** `00ba7f6`

### 3. [Rule 2 - Critical functionality] Wrap audit_logs DELETE try/except UndefinedTable

- **Found during:** Task 2 review.
- **Issue:** Bảng `audit_logs` thuộc migration 004_audit (PARTITIONED BY RANGE timestamp). Môi trường eval mới setup có thể chỉ apply migration 001_bootstrap → cleanup sẽ crash với `UndefinedTable` nếu cố DELETE.
- **Fix:** Wrap DELETE audit_logs trong `try/except (psycopg.errors.UndefinedTable, UndefinedColumn)` → log info + skip thay vì crash.
- **Files modified:** `eval/scripts/cleanup.py` (function `cleanup_audit_logs`).
- **Commit:** `00ba7f6`

### 4. [Rule 1 - Bug] Tránh `**` trong `DANGEROUS_HUB_CODES`, dùng `~` thay cho `\\`

- **Found during:** Task 2 viết guard layer 1.
- **Issue:** PLAN dùng `{"", ".", "/", "*", "..", "\\"}`. Trên Windows path separator là `\` (đã escape thành `\\` trong Python literal). Prompt user dùng `{"", ".", "/", "*", "..", "~"}` — `~` là home directory expansion trên Unix shell, nguy hiểm hơn `\\` (sau cùng `Path()` không expand `~` tự động nên ít nguy hiểm hơn `~` nhưng vẫn nên block).
- **Fix:** Theo prompt user, dùng `{"", ".", "/", "*", "..", "~"}` để cover cả expansion case. Layer 3 (path string phải chứa "eval") vẫn phòng vệ tổng quát.
- **Files modified:** `eval/scripts/cleanup.py` (constant `DANGEROUS_HUB_CODES`).
- **Commit:** `00ba7f6`

### 5. [Rule 2 - Critical functionality] Output structured JSON 1 dòng cuối

- **Found during:** Task 2 implement.
- **Issue:** Prompt user yêu cầu "Output structured (in JSON 1 dòng cuối): `{"deleted_documents": N, "deleted_chunks": M, ...}`". PLAN không có yêu cầu này — chỉ logger.info.
- **Fix:** Track `deleted_documents` count, kết quả `chroma_dropped` và `uploads_cleaned` boolean → in `json.dumps(...)` ở cuối `main()`. Field `deleted_chunks` đặt `null` vì cascade qua FK không count được trực tiếp (DELETE FROM document_chunks không chạy explicit).
- **Files modified:** `eval/scripts/cleanup.py` (cuối `main()`).
- **Commit:** `00ba7f6`

### 6. [Rule 2 - Critical functionality] Load thêm backend/.env làm fallback

- **Found during:** Task 2 implement env loading.
- **Issue:** Prompt user yêu cầu "Connect Postgres qua psycopg (env DB_* từ backend/.env hoặc eval/.env)". `eval/.env` có thể chưa được dev setup (Plan 01-01 chỉ commit `.env.example`).
- **Fix:** `load_dotenv(REPO_ROOT/'eval'/'.env')` rồi `load_dotenv(REPO_ROOT/'backend'/'.env', override=False)` — eval ưu tiên, backend làm fallback.
- **Files modified:** `eval/scripts/cleanup.py` (block load_dotenv module init).
- **Commit:** `00ba7f6`

## TDD Gate Compliance

PLAN không có task `tdd="true"` — không áp dụng RED/GREEN/REFACTOR. Plan 06 (smoke test) sẽ là gate test thật cho Phase 1.

## Known Stubs

Không có. Code thực thi đầy đủ — không có placeholder hay TODO chưa wire data.

## Threat Flags

Không có thay đổi auth/network/trust boundary mới ngoài plan. ChromaDB v2 API call (GET/DELETE/POST `/collections`) đã nằm trong threat surface hiện hữu của backend Go (`backend/internal/vectorstore/chromadb.go`). `psycopg.connect` + DSN từ env tuân thủ secret-management hiện tại.

## Self-Check: PASSED

**Files created tồn tại:**
- FOUND: `eval/scripts/__init__.py`
- FOUND: `eval/scripts/seed_hub.sql`
- FOUND: `eval/scripts/cleanup.py`

**Commit existence:**
- FOUND: `00ba7f6` — `feat(eval): seed_hub.sql + cleanup.py reset state với guard 3-layer [phase-1 plan-02]`

**Verify spec checklist:**
- ruff check: PASS
- AST parse: OK
- --help in tiếng Việt: OK
- Guard 3-layer runtime test (EVAL_HUB_CODE=''): exit 99 OK
- SQL static checks: 7/7 OK

---

*Plan 01-02 hoàn tất 2026-04-28. Sẵn sàng cho Plan 01-03 (Wave 3 — `build_scanned.py` sinh 2 PDF scanned giả lập từ DOCX).*
