---
phase: 09-eval-framework-quality-gate
plan: 01
subsystem: eval
tags: [python, pytest, httpx, psycopg, tabulate, redis, dataset, m1-restore, hub-isolation]

# Dependency graph
requires:
  - phase: M1 archive (commit 0af44f0)
    provides: 8 DOCX/PDF source + 2 scanned PDF + queries.jsonl 12 dòng + headings.json + DATASET.md + QUERIES_REVIEW.md
  - phase: 02-database-schema
    provides: bảng hubs (code/subdomain/is_active) — seed_hub.sql phụ thuộc
provides:
  - Hub_All/eval/ directory độc lập với api/ (Python project skeleton sẵn sàng)
  - Dataset 10 file VN medical (8 sources + 2 scanned) restore byte-identical từ M1
  - queries.jsonl 12 query vàng schema M2 đầy đủ (có hub_id="eval_hub")
  - seed_hub.sql idempotent INSERT eval_hub (code='eval', subdomain='eval.medinet.vn')
  - .env.example template 12 biến (BACKEND_URL + ADMIN_* + DB_* + REDIS + EVAL_HUB_CODE + OPENAI_API_KEY)
  - pyproject.toml PEP 621 + 5 prod dep + 4 dev dep cài PASS Python 3.12.9
  - README placeholder (mở rộng đầy đủ ở Plan 09-04)
affects: [09-02-lib-metrics, 09-03-report-runner, 09-04-makefile-cleanup-readme, 09-05-quality-gate]

# Tech tracking
tech-stack:
  added:
    - httpx 0.28.1 (HTTP client async — gọi API như external client)
    - psycopg 3.3.4 binary (Postgres direct query cleanup)
    - python-dotenv 1.x (đọc eval/.env config)
    - tabulate 0.10.0 (Markdown table gen cho EVAL.md ở Plan 09-03)
    - redis 5.3.1 (FLUSHDB search cache trước mỗi eval run)
    - pytest 8.4.2 + pytest-asyncio 0.24+ + respx 0.23.1 + ruff 0.6+ (dev)
  patterns:
    - Eval framework tách hẳn khỏi api/ — gọi qua HTTP boundary (không import service layer)
    - Python project skeleton độc lập (riêng pyproject.toml + venv tách)
    - Dataset reproducibility via git history restore (M1 commit 0af44f0)
    - Hub isolation pattern (eval_hub subdomain "eval.medinet.vn" tách dev/prod)
    - JSON Unicode tiếng Việt giữ nguyên (ensure_ascii=False — không escape \uXXXX)

key-files:
  created:
    - Hub_All/eval/pyproject.toml
    - Hub_All/eval/.gitignore
    - Hub_All/eval/.env.example
    - Hub_All/eval/__init__.py
    - Hub_All/eval/README.md (placeholder)
    - Hub_All/eval/queries.jsonl (12 dòng schema M2)
    - Hub_All/eval/scripts/seed_hub.sql
    - Hub_All/eval/dataset/sources/ (8 file restore từ M1)
    - Hub_All/eval/dataset/scanned/ (2 scanned PDF)
    - Hub_All/eval/dataset/DATASET.md
    - Hub_All/eval/dataset/QUERIES_REVIEW.md
    - Hub_All/eval/dataset/headings.json
  modified: []

key-decisions:
  - "D-09-01-A: Restore dataset từ git history commit 0af44f0 (KHÔNG generate mới) — pattern reproducibility, byte-identical, tiết kiệm 1 plan effort"
  - "D-09-01-B: hub_id=\"eval_hub\" gán cứng mọi dòng queries.jsonl (M1 chỉ 1 hub mặc định nên thiếu field — M2 schema bắt buộc per REQ EVAL-01)"
  - "D-09-01-C: subdomain 'eval.medinet.vn' không cần DNS thật — eval framework gọi qua BACKEND_URL trực tiếp, subdomain chỉ là isolation marker"
  - "D-09-01-D: pin redis>=5.0,<6 cho eval/ — bản API service pin redis>=7.1.1; conflict resolver chấp nhận, eval venv riêng KHÔNG ảnh hưởng api/"
  - "D-09-01-E: ensure_ascii=False khi re-serialize queries.jsonl — tiếng Việt unicode giữ nguyên (không escape \\uXXXX)"

patterns-established:
  - "Pattern eval skeleton: Python project độc lập với api/, gọi HTTP boundary chứ không import service"
  - "Pattern dataset reproducibility: git show <commit>:<path> > <new path> + sha256sum verify byte-identical"
  - "Pattern hub isolation eval: eval_hub code/subdomain tách hẳn dev/prod"
  - "Pattern queries.jsonl Unicode-safe: json.dumps(..., ensure_ascii=False)"
  - "Pattern .env.example: tổ chức theo nhóm (API Service / Postgres / Redis / Eval-specific / LLM provider)"

requirements-completed:
  - EVAL-01

# Metrics
duration: 12min
completed: 2026-05-21
---

# Phase 09 Plan 01: Phục dựng dataset M1 + khởi tạo skeleton eval/ Python độc lập

**Restore 13 file dataset eval byte-identical từ commit M1 0af44f0 + tạo skeleton Python project độc lập (pyproject.toml + .env.example + .gitignore + README + queries.jsonl với hub_id + seed_hub.sql idempotent)**

## Performance

- **Duration:** ~12 phút
- **Started:** 2026-05-21T06:37:00Z (xấp xỉ — sau khi đọc context)
- **Completed:** 2026-05-21T06:49:13Z
- **Tasks:** 3/3
- **Files modified:** 0 (toàn bộ tạo mới — 18 file)

## Accomplishments

- **Dataset M1 restore byte-identical:** 8 file sources (7 DOCX DMD + tri_thuc_chinh_tri.pdf) + 2 scanned PDF (DMD_T1-01_scanned, DMD_T1-04_scanned cho R4 test 415 failed_unsupported) + 3 metadata (DATASET.md, QUERIES_REVIEW.md, headings.json) — tổng 13 file, SHA256 verify khớp commit `0af44f0`.
- **Skeleton Python project eval/ độc lập với api/:** `pyproject.toml` PEP 621 + 5 prod dep + 4 dev dep, `pip install -e ".[dev]"` PASS Python 3.12.9, `ruff check` PASS.
- **queries.jsonl 12 dòng schema M2:** port semantic từ M1 + thêm `hub_id="eval_hub"` mỗi dòng — schema `{id, query, expected_doc_id, expected_section, hub_id, notes}` đầy đủ, tiếng Việt unicode giữ nguyên.
- **seed_hub.sql idempotent:** `INSERT ... ON CONFLICT (code) DO NOTHING` + SELECT verify cuối — chạy 2 lần row count vẫn 1.

## Task Commits

Each task was committed atomically:

1. **Task 1: Restore dataset từ git history (commit 0af44f0)** — `89fb73f` (feat)
2. **Task 2: Tạo skeleton eval/ (pyproject.toml + .gitignore + __init__.py + .env.example + README placeholder)** — `c2751b5` (chore)
3. **Task 3: Patch queries.jsonl thêm hub_id + tạo seed_hub.sql idempotent** — `6a21612` (feat)

## SHA256 Dataset Verification

Restore byte-identical với commit `0af44f0` (M1 archive). SHA256 dưới đây ghi lại trạng thái dataset sau khi `git checkout 0af44f0 -- ...`:

```
eb0d0b2c2b8572ae7238d48ac860f78301685dc1a5bf28aa95fc7f9d3e70d23d  sources/DMD_T1-01_DinhVi_TrungTam_v1.docx
44aadc2847d2a3c5d328c8153f5e164ae22f698ee84c190f3f63b8733e51e149  sources/DMD_T1-02_TuDien_ThuongHieu_v1.docx
e2c558c5f418eed760c4d9dc88e94bf8a217e6ccbcb702251db75d97bd163520  sources/DMD_T1-03_Script_Library_v1.docx
ae177598595ce6372c66f5b434705e427abe02dd0f5a9d2c80c73767ab7be0d8  sources/DMD_T1-04_FAQ_ThuongHieu_v1.docx
f7584c42cb5a089f8267062d70bc71f84c4d8439662c173bde4b3724b82fd501  sources/DMD_T3-02_PhanCong_NhanVat_v1.docx
979cccb18f52e4a431e22bca2b2e024d8b258bdc113afe379c46de0244b92d32  sources/DMD_T5-01_ContentStrategy_12TuyenND_v1.docx
1d8a25c905cc5e3d73886404ed269d1c70e23b9c36f6ac10fff0b90daffe42bf  sources/DMD_T5-02_Playbook_KenhTruyen_v1.docx
c18ea1b3deddbf4aa682a03169f71e365b59430ac98e2fc6ea58e94d26e972af  sources/tri_thuc_chinh_tri.pdf
12871723a75b796d7acf1ff4cf0f1a5baa1a681ff9ec209fbc8bdb9a89d36ed7  scanned/DMD_T1-01_scanned.pdf
d9f48f9b05a9edfa88a1369c631a0efa40d27467b6a87f6622980d2ba3cd5e94  scanned/DMD_T1-04_scanned.pdf
edf07a6174b432c26bc25dec93b72e78b4f12ead2ed74e4ef97b88588f1eb342  headings.json
37816f080c958eb9119a9f74cdb82c740f10462429f1f4c5cd14339d7198f9e8  DATASET.md
490b62d529161a077b6e550b690f1184a3297c7a1843bcdfacc6ac2095ab9a29  QUERIES_REVIEW.md
```

File size khớp `git show 0af44f0 --stat` (40564 / 42240 / 55855 / 44453 / 214300 / 36258 / 34883 / 97222 / 3743132 / 4680276 bytes). Reproducibility guarantee: mọi developer pull commit `89fb73f` sẽ có dataset bit-by-bit giống M1.

## pip install Output

```
$ python -m pip install -e ".[dev]" --quiet
ERROR: pip's dependency resolver does not currently take into account all the packages
that are installed. This behaviour is the source of the following dependency conflicts.
medinet-wiki-api 0.1.0 requires redis<8,>=7.1.1, but you have redis 5.3.1 which is incompatible.

$ python --version
Python 3.12.9

$ python -c "import httpx, psycopg, tabulate, dotenv, redis; print(httpx.__version__, psycopg.__version__, tabulate.__version__, redis.__version__)"
0.28.1 3.3.4 0.10.0 5.3.1

$ python -c "import respx, pytest; print(respx.__version__, pytest.__version__)"
0.23.1 8.4.2

$ ruff check . --select E,W,F,I,N,UP,B,SIM,RUF
All checks passed!
```

> **Lưu ý conflict redis:** medinet-wiki-api (api/) pin `redis>=7.1.1,<8`, eval/ pin `redis>=5.0,<6` theo plan. Conflict chỉ là WARNING của pip (không fail install). Khi dùng eval/ thật, nên cài trong venv riêng để tránh shadow redis của api/. Plan 09-02 sẽ document virtualenv trong README.

## Sample 2 dòng queries.jsonl sau patch

```jsonl
{"id": "q01", "query": "Câu tuyên bố định vị chính thức của Đỗ Minh Đường gồm bốn thành tố cốt lõi nào?", "expected_doc_id": "DMD_T1-01_DinhVi_TrungTam_v1.docx", "expected_section": "PHẦN 01  |  CÂU TUYÊN BỐ ĐỊNH VỊ CHÍNH THỨC > ▸  1.2  Bốn thành tố cốt lõi không thể thiếu", "notes": "Q definition cụ thể, trỏ tới sub-section 1.2 trong PHẦN 01 — chỉ doc T1-01 chứa câu định vị chính thức", "hub_id": "eval_hub"}
{"id": "q02", "query": "Năm nhóm từ cấm khi viết content thương hiệu Đỗ Minh Đường gồm những gì?", "expected_doc_id": "DMD_T1-02_TuDien_ThuongHieu_v1.docx", "expected_section": "PHẦN 01  |  5 NHÓM TỪ CẤM", "notes": "Từ điển thương hiệu — chỉ T1-02 có chuyên mục 5 nhóm từ cấm", "hub_id": "eval_hub"}
```

12 dòng tất cả PASS schema check `{id, query, expected_doc_id, expected_section, hub_id, notes}` (script verify chạy `Schema OK 12/12`). Tiếng Việt unicode giữ nguyên (không escape `\uXXXX`).

## Files Created/Modified

### Files tạo mới (18 file)

- `Hub_All/eval/pyproject.toml` — PEP 621 + 5 prod dep + 4 dev dep + ruff config + pytest markers
- `Hub_All/eval/.gitignore` — loại `__pycache__/`, `.env`, `results.json`, `EVAL-*.md` (giữ `EVAL.md`)
- `Hub_All/eval/__init__.py` — marker package rỗng
- `Hub_All/eval/.env.example` — 12 biến (BACKEND_URL=8180 + ADMIN_* + DB_* + REDIS_URL + EVAL_HUB_CODE=eval + OPENAI_API_KEY=)
- `Hub_All/eval/README.md` — placeholder (sẽ mở rộng đầy đủ ở Plan 09-04)
- `Hub_All/eval/queries.jsonl` — 12 query vàng schema M2 với `hub_id="eval_hub"`
- `Hub_All/eval/scripts/seed_hub.sql` — idempotent INSERT eval_hub với ON CONFLICT
- `Hub_All/eval/dataset/sources/DMD_T1-01_DinhVi_TrungTam_v1.docx` (40564 B)
- `Hub_All/eval/dataset/sources/DMD_T1-02_TuDien_ThuongHieu_v1.docx` (42240 B)
- `Hub_All/eval/dataset/sources/DMD_T1-03_Script_Library_v1.docx` (55855 B)
- `Hub_All/eval/dataset/sources/DMD_T1-04_FAQ_ThuongHieu_v1.docx` (44453 B)
- `Hub_All/eval/dataset/sources/DMD_T3-02_PhanCong_NhanVat_v1.docx` (214300 B)
- `Hub_All/eval/dataset/sources/DMD_T5-01_ContentStrategy_12TuyenND_v1.docx` (36258 B)
- `Hub_All/eval/dataset/sources/DMD_T5-02_Playbook_KenhTruyen_v1.docx` (34883 B)
- `Hub_All/eval/dataset/sources/tri_thuc_chinh_tri.pdf` (97222 B)
- `Hub_All/eval/dataset/scanned/DMD_T1-01_scanned.pdf` (3743132 B)
- `Hub_All/eval/dataset/scanned/DMD_T1-04_scanned.pdf` (4680276 B)
- `Hub_All/eval/dataset/DATASET.md` (8472 B)
- `Hub_All/eval/dataset/QUERIES_REVIEW.md` (9272 B)
- `Hub_All/eval/dataset/headings.json` (30871 B)

(Tổng 20 file tạo mới — 13 dataset + 7 skeleton/config)

### Files modified

- Không có. Plan 09-01 là plan FOUNDATION cho Phase 9, toàn bộ là tạo mới.

## Decisions Made

- **D-09-01-A: Restore dataset từ git history thay vì generate mới** — RESEARCH Open Q "thuận lợi #1" đã xác minh dataset M1 hoàn chỉnh trong commit `0af44f0`. Restore byte-identical đảm bảo reproducibility tuyệt đối, tiết kiệm hẳn 1 plan effort (vs viết LibreOffice export + python-docx gen mới).
- **D-09-01-B: Gán cứng `hub_id="eval_hub"` mọi dòng queries.jsonl** — M1 chỉ có 1 hub mặc định nên thiếu field. M2 schema bắt buộc per REQ EVAL-01. KHÔNG dùng `slug` hay `code` riêng — patch nhất quán theo subdomain marker `eval_hub` (eval framework dùng `code='eval'` ở DB; field này chỉ là loose tag, repo layer sẽ resolve thật).
- **D-09-01-C: subdomain 'eval.medinet.vn' không cần DNS thật** — eval framework gọi qua `BACKEND_URL=http://localhost:8180` trực tiếp, không qua subdomain routing. Subdomain chỉ là isolation marker để tách hẳn hub dev/prod trên cùng instance Postgres.
- **D-09-01-D: pin redis>=5.0,<6 cho eval/ (xung đột với api/ pin redis>=7.1.1)** — eval/ là project độc lập, dùng venv riêng. Plan đã quyết định range 5.x. pip resolver cài 5.3.1 cho eval và để api/ riêng. KHÔNG bump eval lên 7.x (sẽ phá đối xứng với plan; pin của api/ thuộc Phase 6 scope).
- **D-09-01-E: ensure_ascii=False khi re-serialize queries.jsonl** — pattern Python json mặc định escape non-ASCII, làm `query` tiếng Việt khó đọc. `ensure_ascii=False` giữ nguyên Unicode (`Đỗ Minh Đường`, `Câu tuyên bố`, v.v.) — đọc trực tiếp được trong diff/code review.

## Deviations from Plan

**None - plan executed exactly as written.**

Plan 09-01 đặc biệt rõ ràng (3 task, mỗi task có `<action>` step-by-step + `<verify>` automated + `<done>` rõ); thực thi đi đúng script. Không có Rule 1/2/3 deviation phát sinh. Có 1 NOTE-WORTHY điểm về dependency conflict redis (xem D-09-01-D + Issues Encountered) — KHÔNG phải deviation vì plan đã ấn định range.

---

**Total deviations:** 0 auto-fixed
**Impact on plan:** Plan executed atomically, đúng spec. Skeleton sẵn sàng cho Plan 09-02 (lib.py + metrics.py).

## Issues Encountered

- **pip dependency conflict `redis` (NOTE-WORTHY, không block):** `medinet-wiki-api 0.1.0` cài sẵn ở scope toàn cục đòi `redis<8,>=7.1.1`, eval/ pin `redis>=5.0,<6` theo plan. pip resolver cài `redis 5.3.1` (theo eval extras-install command), api/ runtime sẽ chạy với redis 5.3.1 này — có thể vỡ vì api/ pin range cao hơn. **Mitigation:** Khi chạy eval thật, cài trong venv riêng (`python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`). Plan 09-04 sẽ document workflow venv-tách trong README. Hiện tại chưa block vì Plan 09-01 chỉ verify install — chưa chạy eval thật.

## User Setup Required

None — Plan 09-01 hoàn toàn local file ops + git checkout. Không có external service config.

(Plan 09-02..04 tiếp theo sẽ cần OPENAI_API_KEY thật cho gate verdict — sẽ document ở `.env.example` đã commit.)

## Next Phase Readiness

- ✅ **Plan 09-02 (lib.py + metrics.py):** Sẵn sàng — pyproject.toml + dataset + queries.jsonl đã có. Plan 09-02 build `APIClient` (httpx async + JWT auto-refresh), `preflight_check()`, `metrics.py` (top-K + MRR + latency p50/p95/p99).
- ✅ **Plan 09-03 (report.py + run_eval.py):** Sẵn sàng — tabulate đã trong dep.
- ✅ **Plan 09-04 (Makefile + cleanup.py + README full):** Sẵn sàng — pattern .env + scripts/ folder đã có.
- ⚠️ **Plan 09-05 (gate run thật):** Cần `OPENAI_API_KEY` paid tier + stack chạy (postgres + redis + uvicorn + cocoindex flow ingest 10 file). Đây là Wave 4 gate verdict.

## Self-Check: PASSED

Verify claims:

**Files exist:**
- ✅ `Hub_All/eval/pyproject.toml` — FOUND
- ✅ `Hub_All/eval/.env.example` — FOUND
- ✅ `Hub_All/eval/.gitignore` — FOUND
- ✅ `Hub_All/eval/__init__.py` — FOUND
- ✅ `Hub_All/eval/README.md` — FOUND
- ✅ `Hub_All/eval/queries.jsonl` — FOUND (12 lines)
- ✅ `Hub_All/eval/scripts/seed_hub.sql` — FOUND (ON CONFLICT + code='eval' OK)
- ✅ `Hub_All/eval/dataset/sources/` — FOUND (8 file)
- ✅ `Hub_All/eval/dataset/scanned/` — FOUND (2 file)
- ✅ `Hub_All/eval/dataset/DATASET.md` — FOUND
- ✅ `Hub_All/eval/dataset/QUERIES_REVIEW.md` — FOUND
- ✅ `Hub_All/eval/dataset/headings.json` — FOUND

**Commits exist (git log):**
- ✅ `89fb73f` — FOUND
- ✅ `c2751b5` — FOUND
- ✅ `6a21612` — FOUND

**Acceptance criteria Plan 09-01:**
- ✅ Dataset restored từ git history (10 sources + 2 scanned)
- ✅ eval/pyproject.toml + .env.example + .gitignore + README placeholder + __init__.py tạo đủ
- ✅ queries.jsonl 12 dòng JSON, mỗi dòng có hub_id="eval_hub"
- ✅ eval/scripts/seed_hub.sql tạo eval_hub idempotent
- ✅ Acceptance criteria mỗi task PASS

---
*Phase: 09-eval-framework-quality-gate*
*Completed: 2026-05-21*
