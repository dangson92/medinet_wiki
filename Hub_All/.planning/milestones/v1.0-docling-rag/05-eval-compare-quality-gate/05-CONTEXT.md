# CONTEXT — Phase 5: Eval Compare & Quality Gate

**Phase:** 5 / 5 (cuối M1)
**Milestone:** M1 — RAG Quality with Docling
**Goal:** Có báo cáo định lượng `eval/EVAL.md` so sánh extraction + retrieval giữa `RAG_EXTRACTOR=native` và `=docling` trên cùng dataset; gate milestone pass khi top-3 hit rate **tăng ≥ 15 điểm phần trăm** HOẶC đạt ngưỡng tuyệt đối ≥ 75%. Có smoke test `make eval-smoke` đảm bảo Docling thực sự được dùng (không fallback ngầm).
**Requirements:** EVAL-02..05 (4 REQ)
**Ngày discuss:** 2026-05-04 (auto mode — defaults applied, log dưới)

---

## Decisions Locked (auto mode)

### A. Cấu trúc thư mục `eval/` mở rộng

Reuse skeleton Phase 1, thêm 4 file mới + 1 EVAL.md output:

```
eval/
├── README.md                    # update — thêm section eval compare
├── pyproject.toml               # update — thêm 1 dep nếu cần (tabulate cho Markdown table)
├── baseline.py                  # GIỮ NGUYÊN (Phase 1) — chạy với mode=native
├── baseline_native.json         # GIỮ NGUYÊN (commit f37cd96) — baseline 75%
├── baseline_docling.json        # MỚI Phase 5 — output từ run_docling.py
├── lib.py                       # MỚI — shared API client + login + poll (extract từ baseline.py)
├── run_docling.py               # MỚI — Plan 05-01: chạy ingestion với RAG_EXTRACTOR=docling
├── run_extraction_compare.py    # MỚI — Plan 05-03: compare chunks/heading/table preservation
├── run_retrieval_eval.py        # MỚI — Plan 05-04: 12 query × 2 mode → top-K + MRR
├── run_compare.py               # MỚI — Plan 05-02: orchestrator gọi 03 + 04 → tổng hợp
├── EVAL.md                      # MỚI — Plan 05-05: final report (commit cuối)
└── scripts/                     # giữ nguyên Phase 1 (cleanup, build_scanned, extract_headings, seed_hub)
```

**Lý do:** giữ `baseline.py` + `baseline_native.json` immutable (đã có 75% baseline). Tạo file riêng cho Docling mode để diff dễ đọc + audit.

### B. Snapshot schema (`baseline_docling.json`)

**Identical schema với `baseline_native.json`** (đã chốt Phase 1):

```json
{
  "run_id": "2026-05-XXTHH:MM:SSZ",
  "extractor_mode": "docling",
  "embedder_provider": "openai",
  "embedder_model": "text-embedding-3-large",
  "embedder_dim": 3072,
  "documents": [
    {"doc_id": "...", "filename": "...", "status": "completed|error",
     "chunks_count": N, "avg_chunk_tokens": F,
     "headings_gold_count": N,
     "extractor_used": "docling"  // mới — đọc từ documents.extractor_used (CFG-06)
    }
  ],
  "retrieval": {
    "top_1_hit_rate": 0.xxx, "top_3_hit_rate": 0.xxx, "top_5_hit_rate": 0.xxx,
    "mrr": 0.xxx,
    "per_query": [...]
  }
}
```

**Embedder lock verify:** script `run_docling.py` PHẢI assert `embedder_provider/model/dim` giống `baseline_native.json` — nếu khác → fail loud (gate fairness).

### C. Refactor: extract `eval/lib.py` shared module

Phase 1 `baseline.py` 588 dòng có pattern reusable: pre-flight, login, get_hub_id, upload+poll, search, snapshot. Phase 5 cần dùng lại → extract sang `eval/lib.py`:

```python
# eval/lib.py (mới)
class APIClient:
    def __init__(self, base_url, email, password): ...
    def login(self): ...
    def refresh_if_expired(self): ...
    def get_hub_id(self, code): ...
    def upload_and_wait(self, hub_id, file_path, timeout=180): ...
    def search(self, hub_id, query, top_k=5, min_score=0.0): ...
    def reindex(self, doc_id, extractor): ...   # mới — dùng CFG-07 endpoint

def preflight(backend_url, db_dsn, chroma_url, hub_code) -> None: ...
def get_embedder_config(client) -> dict: ...    # provider, model, dim
def upload_dataset(client, hub_id, dataset_dir) -> list[DocResult]: ...
def evaluate_queries(client, hub_id, queries) -> RetrievalMetrics: ...

@dataclass
class DocResult:
    doc_id: str; filename: str; status: str; chunks_count: int
    avg_chunk_tokens: float; extractor_used: str
```

`baseline.py` Phase 1 KHÔNG sửa (immutable). `run_docling.py` Phase 5 import `lib.py`. Defer refactor `baseline.py` để dùng `lib.py` sang milestone hardening.

### D. Run mode comparison strategy

**Quy trình `eval/run_compare.py`:**

1. **Pre-condition check**: `baseline_native.json` tồn tại, embedder config khớp.
2. **Setup**: chạy `cleanup.py` reset eval_hub.
3. **Phase A — Run Docling mode** (`run_docling.py`):
   - PUT `/api/rag-config` để force `extractor_mode=docling` runtime (qua CFG-03).
   - Upload 10 file (lib.upload_dataset).
   - Poll completion (timeout cao hơn baseline vì Docling chậm hơn — 300s/file).
   - Verify `documents.extractor_used='docling'` cho 8/10 file (2 scanned PDF có thể vẫn fail nếu Docling OCR tệ).
   - Run 12 query, snapshot `baseline_docling.json`.
4. **Phase B — Compare** (`run_compare.py` orchestrator):
   - Load 2 snapshot.
   - Compute diff per-document + per-query.
   - Sinh `EVAL.md` với gate verdict.

**Restore mode sau run:** PUT `/api/rag-config` về `auto` để không ảnh hưởng dev tiếp theo.

### E. Quality gate logic (EVAL-04)

**Gate cứng** trong `run_compare.py`:

```python
def evaluate_gate(native: dict, docling: dict) -> tuple[str, str]:
    """Returns (verdict, reason). verdict ∈ {PASS, FAIL}."""
    n3 = native["retrieval"]["top_3_hit_rate"]
    d3 = docling["retrieval"]["top_3_hit_rate"]
    delta = d3 - n3
    
    if delta >= 0.15:
        return "PASS", f"top-3 cải thiện {delta*100:+.1f}pp ({n3*100:.1f}% → {d3*100:.1f}%)"
    if d3 >= 0.75:
        return "PASS", f"top-3 đạt {d3*100:.1f}% (≥ 75% tuyệt đối, dù delta {delta*100:+.1f}pp)"
    return "FAIL", f"top-3 chỉ {d3*100:.1f}%, delta {delta*100:+.1f}pp — chưa đạt gate ≥ +15pp HOẶC ≥ 75%"
```

**`run_compare.py` exit code:** 0 nếu PASS, 1 nếu FAIL → CI có thể block merge nếu cần.

**Nhưng `EVAL.md` vẫn được sinh** dù FAIL — chứa số liệu để debug.

### F. EVAL.md report structure

```markdown
# EVAL — M1 RAG Quality with Docling

**Ngày chạy:** 2026-05-XX
**Verdict:** PASS / FAIL
**Reason:** <1 dòng tóm tắt>

## 1. Setup
- Dataset: 10 file (8 DMD + 1 PDF + 2 scanned)
- Queries: 12 truy vấn vàng
- Embedder: openai/text-embedding-3-large 3072d (locked)
- Native run: 2026-04-28 (commit f37cd96)
- Docling run: 2026-05-XX

## 2. Retrieval Comparison
| Metric | Native | Docling | Delta |
|---|---|---|---|
| top-1 | 0.750 | 0.XXX | +X.X pp |
| top-3 | 0.750 | 0.XXX | +X.X pp |
| top-5 | 0.750 | 0.XXX | +X.X pp |
| MRR   | 0.750 | 0.XXX | +X.X |

## 3. Per-Query Diff
| Q | Expected | Native rank | Docling rank | Verdict |
|---|---|---|---|---|
| q01 | T1-01 | 1 | 1 | unchanged |
| q05 | T3-02 | None | 1 | FIXED |
| q09 | scanned-T1-01 | None | 1 | FIXED |
| q10 | scanned-T1-04 | None | 1 | FIXED |
| ... | ... | ... | ... | ... |

## 4. Per-Document Extraction Quality
| Doc | Native chunks | Docling chunks | Heading recall | Table preservation |
|---|---|---|---|---|
| DMD_T1-01.docx | 152 | NN | X% | X/X tables |
| ...

## 5. Smoke Verification
- `make eval-smoke` last run: 2026-05-XX → status (Docling chunks indexed, `is_table=true` ≥ 1)

## 6. Conclusion
<text trình bày verdict + recommendation>

## 7. Defer for M2/M3
- (list các gap còn lại không pass — vd reranker cho query X)
```

### G. `make eval-smoke` Makefile target (EVAL-05)

Thêm vào `Makefile` (hoặc tạo `eval/Makefile`):

```makefile
eval-smoke:
	@python -c "import sys; sys.path.insert(0, 'eval'); from lib import APIClient, preflight; \
		preflight('http://localhost:8180', '$$DB_DSN', 'http://localhost:8000', 'eval'); \
		c = APIClient('http://localhost:8180', 'admin@medinet.vn', 'Admin@123'); \
		c.login(); \
		hub = c.get_hub_id('eval'); \
		doc = c.upload_and_wait(hub, 'eval/dataset/sources/DMD_T1-01_DinhVi_TrungTam_v1.docx'); \
		assert doc['extractor_used'] == 'docling', f'Expected docling, got {doc[\"extractor_used\"]}'; \
		results = c.search(hub, 'tóm tắt định vị thương hiệu', top_k=5); \
		has_table = any(r.get('metadata', {}).get('is_table') for r in results); \
		assert has_table, 'Expected ≥ 1 chunk with is_table=true'; \
		print('SMOKE OK: Docling extractor used + table chunk indexed')"

eval-baseline-docling:
	python eval/run_docling.py

eval-compare:
	python eval/run_compare.py

eval-all: eval-baseline-docling eval-compare
```

### H. Out of Scope Phase 5 (defer)

- ❌ A/B với multiple embedding model (giữ OpenAI lock per Phase 1).
- ❌ Statistical significance test (12 queries quá ít cho t-test — chỉ trình bày diff thô).
- ❌ Auto regression CI (defer M2 hardening — cần GitHub Actions setup).
- ❌ Visual dashboard cho eval (defer M3 nếu cần).
- ❌ Reranker eval (defer M3 backlog 999.2).
- ❌ Eval với dataset thật từ production (M2 — cần hợp tác với Medinet).

### I. Dependencies

**Python deps mới cần thêm `eval/pyproject.toml`:**
- `tabulate>=0.9` — sinh Markdown table từ data structure (cho EVAL.md).
- (existing: httpx, python-docx, pypdf, psycopg, dotenv — đủ).

**Backend deps:** zero mới (reuse endpoint hiện có CFG-03 PUT để switch mode, CFG-07 reindex nếu cần).

---

## Implementation Tasks (planner sẽ decompose 5 plan)

### Plan 05-01: `lib.py` shared + `run_docling.py`
- Extract `eval/lib.py` từ pattern `baseline.py`.
- Tạo `run_docling.py`: pre-flight → PUT mode docling → upload 10 file → poll → snapshot → restore mode auto.
- Output: `eval/baseline_docling.json`.
- REQ: foundation cho Plan 02-04.

### Plan 05-02: `run_extraction_compare.py` (EVAL-02)
- Load 2 snapshot.
- Per-document compare: `chunks_count` diff, `avg_chunk_tokens` diff.
- **Heading recall**: load `eval/dataset/headings.json` (Phase 1) → cho mỗi doc, query `documents` chunks via `GET /api/documents/{id}/chunks` (or DB direct), check chunks có chứa heading text → tính recall.
- **Table preservation**: cho mỗi DOCX có table (Phase 1 đã label), check `documents_chunks.metadata.is_table=true` count.
- Sinh JSON intermediate `eval/extraction_compare.json`.

### Plan 05-03: `run_retrieval_eval.py` (EVAL-03)
- Load 12 queries từ `eval/dataset/queries.jsonl`.
- Cho mỗi mode (native, docling) chạy 12 query qua `/api/search`.
- Compute top-1/3/5 hit rate + MRR.
- Sinh JSON intermediate `eval/retrieval_eval.json`.

### Plan 05-04: `run_compare.py` orchestrator + EVAL.md generator (EVAL-04)
- Orchestrate Plan 02 + 03.
- Apply quality gate logic.
- Sinh `eval/EVAL.md` qua template + tabulate.
- Exit code 0/1 theo gate.

### Plan 05-05: `make eval-smoke` + Makefile + final commit (EVAL-05)
- Thêm Makefile root targets `eval-smoke`, `eval-baseline-docling`, `eval-compare`, `eval-all`.
- Update `eval/README.md` với hướng dẫn chạy.
- Smoke test code path cuối cùng.

---

## Auto-mode default decisions log

| Decision area | Auto pick | Rationale |
|---|---|---|
| Snapshot file naming | `baseline_docling.json` | Symmetric với `baseline_native.json` Phase 1 |
| Refactor strategy | Extract `lib.py` shared, KHÔNG sửa `baseline.py` | Giữ Phase 1 immutable + Phase 5 code clean |
| Quality gate exit code | Hard exit 1 nếu FAIL | CI-friendly, có thể relax bằng env nếu cần |
| EVAL.md format | Markdown với tabulate tables | Diff git dễ, render GitHub OK |
| Smoke endpoint | `make eval-smoke` 1 file e2e | Nhanh (~30s) đủ verify Docling work |
| Heading recall query | DB direct (psycopg) thay API | Tránh expose endpoint internal, nhanh hơn |
| Restore mode sau run | Auto restore về `auto` mode | Không ảnh hưởng dev tiếp theo |
| Embedder lock verify | Hard fail nếu khác Phase 1 | Fairness gate tuyệt đối |
| Stats sig test | Skip | 12 queries quá ít — chỉ trình bày diff thô |
| Reranker eval | Defer M3 | Ngoài scope M1 |

## Rủi ro & Câu hỏi mở

- **Rủi ro 1:** Docling runtime chưa setup (Docker/Podman/WSL block từ Phase 2-4). Phase 5 code hoàn thiện được nhưng RUNTIME quality gate eval cần Docling service real. Mitigation: Plan 05 code 100%, runtime defer giống Phase 2-4.

- **Rủi ro 2:** Switch mode runtime (PUT extractor_mode=docling) trong khi worker pool đang process job native → race condition. Mitigation: cleanup eval_hub trước khi switch + chờ all workers idle (poll DB `WHERE status IN ('pending','processing')` = 0).

- **Rủi ro 3:** Docling extract chậm (5-15s/file) × 10 file × 100-300 chunks/file × OpenAI embedding API latency = run time có thể 30-60 phút. Mitigation: chấp nhận + log progress.

- **Rủi ro 4:** Gate FAIL → user thất vọng. Mitigation: EVAL.md trình bày rõ root cause, recommend reranker / hybrid retrieval / data improvement (như đã thấy với BS Lê Phương — content gap chứ không phải RAG bug).

## Deferred Ideas

- 999.13 — Auto eval CI (GitHub Actions chạy mỗi PR vào pipeline.go).
- 999.14 — Visual dashboard eval (Streamlit / web UI để admin xem metrics history).
- 999.15 — Larger eval dataset (100+ queries từ production logs khi có data thật).

---

## Downstream

**gsd-planner Phase 5 sẽ đọc CONTEXT này:**
- 5 plan tương ứng EVAL-02..05 + 1 plan foundation lib.
- Mỗi plan có spec rõ schema input/output.
- Quality gate logic chốt cứng.
- EVAL.md template chốt structure.

---

*Last updated: 2026-05-04 (auto mode — defaults applied tự động, log dưới mục "Auto-mode default decisions log")*
