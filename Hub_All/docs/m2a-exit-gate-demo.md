# M2a EXIT GATE — Manual Demo Script (REVISION 2)

**Phase:** 4 (CocoIndex Flow MVP + Document Ingest)
**Created:** 2026-05-14 (Plan 04-06 REVISION 2 — M2a EXIT GATE proxy)
**Mục đích:** Verify end-to-end pipeline upload DOCX VN → chunks pgvector. Gating decision tiếp tục M2b (Phase 5-10).

**REVISION 2 cập nhật:**

- Cocoindex 1.0.3 (KHÔNG support LISTEN/NOTIFY) — A4 BackgroundTasks trigger qua FastAPI.
- KHÔNG còn target `make cocoindex setup` riêng (cũ M2 prototype) — Plan 04-03 REVISION 2 wire `setup_cocoindex` vào FastAPI lifespan (auto chạy khi uvicorn start).
- Watchdog timeout 5 phút (Plan 04-05 REVISION 2 — headroom cho cocoindex update_blocking documents lớn).

---

## Tổng quan

Theo `.planning/PROJECT.md` (R3 mitigation) và `.planning/ROADMAP.md` (line 158-159), **M2a EXIT GATE** là gate cuối Phase 4 trước khi cho phép Phase 5+ chạy. User chạy demo này, accept = condition để tiếp tục M2b. Reject = STOP, KHÔNG pivot lần 3 (trừ khi E1-E5 trigger).

5/5 ROADMAP success criteria (Phase 4):

1. POST `/api/documents/upload` (multipart, DOCX VN) → 202 + `document_id`, file lưu `file_store/<uuid>.docx`, row `documents` `status='pending'` + `last_heartbeat=NOW()` bootstrap trong <500ms.
2. Trong <5s sau upload, A4 BackgroundTask `trigger_cocoindex_update` chạy → `cocoindex_app.update_blocking()` → INSERT chunks → UPDATE documents `status='completed'`; `GET /api/documents/:id` trả `chunk_count > 0`, `chunks` table rows với `hub_id` đúng, `vector` dim=1536, `content_hash BYTEA` set.
3. Upload scanned PDF VN → **HTTP 415** envelope `{success:false, error:{code:"UNSUPPORTED_FORMAT"...}}`; `documents.status='failed_unsupported'` (BLOCKER #3 router synchronous early-detect — Plan 04-04 REVISION 2). KHÔNG add BackgroundTask cho scanned row.
4. Heartbeat watchdog PASS: kill cocoindex worker giữa flow → sau **5 phút** (REVISION 2 timeout — Plan 04-05), status `processing → failed` (chỉ flip nếu `last_heartbeat IS NOT NULL` + stale — WARNING #7).
5. Content-hash incremental: upload cùng file 2 lần (different document_id) → cocoindex memo hit (KHÔNG re-embed) + stable_chunk_id uuid5 deterministic.

---

## Tiền điều kiện

- [ ] Docker Desktop chạy
- [ ] `cd Hub_All && cp api/.env.example api/.env` rồi điền giá trị thực (OPENAI_API_KEY required cho dimensions=1536)
- [ ] `.env` có `COCOINDEX_DB=Hub_All/.cocoindex/state.lmdb` (Q5 — Plan 04-03 REVISION 2)
- [ ] `cd Hub_All/api && uv sync --extra dev` (cài deps)
- [ ] `cd Hub_All/api && make keys` (sinh JWT RS256 keypair — `keys/private.pem` + `keys/public.pem`)
- [ ] DOCX VN sample tại `Hub_All/docs/fixtures/khám-bệnh-mẫu.docx` (operator chuẩn bị thủ công, hoặc dùng python-docx runtime tạo qua snippet trong Bước 4)

---

## Bước 1 — Khởi động stack Docker Compose

```bash
cd Hub_All
docker compose up -d postgres redis
docker compose ps                          # cả 2 service healthy
docker compose logs postgres | tail -20    # verify CREATE EXTENSION vector OK
```

**Expected:** 2 service `postgres` (image `pgvector/pgvector:pg16`) + `redis` (image `redis:7-alpine`) lên healthy. PostgreSQL log có dòng `CREATE EXTENSION vector` thành công.

---

## Bước 2 — Migrate (cocoindex auto setup qua lifespan REVISION 2)

```bash
cd Hub_All/api
make migrate-up                            # Alembic upgrade head (0001 + 0002)
make migrate-check                         # No drift
```

**REVISION 2 — KHÔNG còn target `make cocoindex setup` riêng (cũ M2 prototype):** Plan 04-03 REVISION 2 wire `setup_cocoindex` vào FastAPI lifespan. Khi uvicorn start (Bước 3), lifespan auto chạy: register @coco.lifespan + coco.start_blocking + cocoindex_app.update_blocking() initial backfill.

**Verify schema:**

```bash
docker exec -it medinet-postgres psql -U medinet -d medinet_central \
  -c "\\d documents"
# → Columns documents có: last_heartbeat, attempts, error_message, status (CHECK enum 5 giá trị).

docker exec -it medinet-postgres psql -U medinet -d medinet_central \
  -c "SELECT indexname FROM pg_indexes WHERE tablename='documents'"
# → ix_documents_status_last_heartbeat tồn tại (Plan 04-01 INGEST-06).

docker exec -it medinet-postgres psql -U medinet -d medinet_central \
  -c "SELECT indexname FROM pg_indexes WHERE tablename='chunks'"
# → ix_chunks_vector_hnsw tồn tại (Migration 0001 — Decision B1 Alembic owns).
```

---

## Bước 3 — Khởi động FastAPI + seed admin (lifespan auto cocoindex setup REVISION 2)

```bash
cd Hub_All/api
docker compose up -d api                   # hoặc uv run uvicorn app.main:app --port 8080
# Đọc log uvicorn: phải có dòng `cocoindex_setup_ok` + `cocoindex_initial_backfill_complete`
# (Plan 04-03 REVISION 2 lifespan auto setup cocoindex).

curl -s http://localhost:8080/healthz | jq
# → {"success":true,"data":{"status":"ok"},...}

curl -s http://localhost:8080/readyz | jq
# → {"success":true,"data":{"db":"ok","redis":"ok","cocoindex":"ok","jwt":"ok"},...}
```

**Seed admin user qua psql** (Phase 3 mới chỉ có pwdlib, user tạo qua SQL trực tiếp với Go-seed hash đã cross-compat verified Plan 03-03):

```bash
# Hash cho password "Admin@123" (R6 verified hash):
GO_SEED_HASH='$argon2id$v=19$m=65536,t=3,p=4$gpKFndFoG6bcXrx7R60sag$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c'

docker exec -it medinet-postgres psql -U medinet -d medinet_central -c \
  "INSERT INTO users (email, password_hash, full_name, role, is_active, created_at, updated_at) \
   VALUES ('admin@medinet.vn', '$GO_SEED_HASH', 'System Admin', 'admin', TRUE, NOW(), NOW())"

# Seed hub_y_te
docker exec -it medinet-postgres psql -U medinet -d medinet_central -c \
  "INSERT INTO hubs (slug, name, is_active, created_at) VALUES ('hub_y_te', 'Y Tế', TRUE, NOW()) RETURNING id"
# → ghi nhớ UUID hub_id để dùng bước 4
```

---

## Bước 4 — Upload DOCX tiếng Việt (A4 BackgroundTasks REVISION 2)

Optional sinh DOCX VN runtime nếu chưa có sample:

```bash
cd Hub_All
mkdir -p docs/fixtures
uv run --project api python3 -c "
from docx import Document
d = Document()
d.add_paragraph('Mục 1. KHÁM TỔNG QUÁT')
d.add_paragraph('Bệnh nhân được khám lâm sàng tỉ mỉ.')
d.add_paragraph('Mục 2. XÉT NGHIỆM')
d.add_paragraph('Làm xét nghiệm máu và siêu âm.')
d.save('docs/fixtures/khám-bệnh-mẫu.docx')
"
```

```bash
# Login
TOKEN=$(curl -s -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@medinet.vn","password":"Admin@123"}' \
  | jq -r '.data.access_token')
echo "TOKEN length: ${#TOKEN}"  # phải > 100

HUB_ID="<paste UUID hub_y_te từ bước 3>"

# Upload — Plan 04-04 REVISION 2 router add BackgroundTask trigger_cocoindex_update
curl -s -X POST http://localhost:8080/api/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@docs/fixtures/khám-bệnh-mẫu.docx" \
  -F "hub_id=$HUB_ID" | jq

# Expected: HTTP 202 + {"success":true,"data":{"document_id":"<uuid>","status":"pending","filename":"khám-bệnh-mẫu.docx"},...}
DOC_ID="<paste document_id>"
```

**Poll status đợi BackgroundTask trigger_cocoindex_update + cocoindex_app.update_blocking + count chunks + UPDATE status:**

```bash
for i in {1..30}; do
  STATUS=$(curl -s "http://localhost:8080/api/documents/$DOC_ID" \
    -H "Authorization: Bearer $TOKEN" | jq -r '.data.status')
  echo "[$i] status=$STATUS"
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ] || [ "$STATUS" = "failed_unsupported" ]; then break; fi
  sleep 1
done

curl -s "http://localhost:8080/api/documents/$DOC_ID" \
  -H "Authorization: Bearer $TOKEN" | jq
# → status:"completed", chunk_count > 0
```

**Note REVISION 2:** A4 BackgroundTask chạy SAU response 202 → status mất ~2-5s để chuyển 'pending' → 'completed' (cocoindex_app.update_blocking + count chunks + UPDATE status). 30s timeout đủ headroom cho document VN bình thường.

---

## Bước 5 — Verify chunks pgvector

```bash
docker exec -it medinet-postgres psql -U medinet -d medinet_central -c \
  "SELECT id, hub_id, vector_dims(vector) AS dim, content_hash IS NOT NULL AS hash_set, \
          LEFT(content, 60) AS preview \
   FROM chunks WHERE document_id = '$DOC_ID' \
   ORDER BY created_at LIMIT 5"
```

**Expected rows:** Mỗi chunk có:

- `hub_id` = UUID hub_y_te (match upload — ChunkRow dataclass wire hub_id từ doc_row).
- `dim` = **1536** (R1 mitigation).
- `hash_set` = **t** (content_hash BYTEA set — ChunkRow.content_hash sha256 wire).
- `preview` chứa nội dung tiếng Việt "Mục", "Khám", "Bệnh"...

**Verify scanned PDF rejection (Bước 5b — BLOCKER #3 verify):**

```bash
# Tạo PDF scanned mock (pypdf parse empty)
# Hoặc dùng scan PDF VN thật từ Medinet sample

curl -s -X POST http://localhost:8080/api/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@docs/fixtures/scan-vn.pdf" \
  -F "hub_id=$HUB_ID" -w "\nHTTP %{http_code}\n" | jq

# Expected: HTTP 415 + envelope {error.code:"UNSUPPORTED_FORMAT"}.
# Plan 04-04 REVISION 2 BLOCKER #3 — router/service synchronous early-detect scanned PDF.
# A4 REVISION 2: KHÔNG add BackgroundTask cho scanned (status final ngay).

# Verify DB row status='failed_unsupported' đã INSERT (service.create INSERT trước khi raise)
docker exec -it medinet-postgres psql -U medinet -d medinet_central -c \
  "SELECT filename, status FROM documents WHERE filename LIKE '%scan%' ORDER BY created_at DESC LIMIT 1"
# → status='failed_unsupported'
```

---

## Acceptance criteria — M2a EXIT GATE

Mỗi tiêu chí PASS = check ✓:

- [ ] **AC1 (INGEST-04)**: Upload DOCX VN → 202 với `document_id`, file lưu `file_store/`, row status='pending' + last_heartbeat=NOW() bootstrap trong <500ms.
- [ ] **AC2 (INGEST-02 + INGEST-03 + A4 REVISION 2)**: <30s sau upload, A4 BackgroundTask trigger_cocoindex_update set status='completed', chunks table có rows hub_id đúng + vector dim=1536 + content_hash set. **A4 strategy preserves <5s SLA** vì cocoindex chạy ngay sau response 202 (KHÔNG poll latency LISTEN/NOTIFY).
- [ ] **AC3 (R4 / INGEST-02 + BLOCKER #3 REVISION 2)**: Scanned PDF → HTTP 415 + status='failed_unsupported' (router synchronous early-detect — Plan 04-04 REVISION 2 strategy A) + KHÔNG add BackgroundTask cocoindex.
- [ ] **AC4 (P8 / INGEST-06 + WARNING #7 + REVISION 2 timeout 5 phút)**: Kill cocoindex worker (TERM signal vào api container) → sau **5 phút** (Plan 04-05 REVISION 2 timeout configurable Settings.watchdog_timeout_seconds=300), status='processing' với `last_heartbeat IS NOT NULL` (bootstrap) + stale → flip 'failed' (manual stress test — optional cho demo).
- [ ] **AC5 (D-1 / cocoindex memo + stable_chunk_id REVISION 2)**: Upload cùng file 2 lần (different document_id) → cocoindex memo hit qua content fingerprint (KHÔNG re-embed). stable_chunk_id uuid5 namespace deterministic per (doc_id, chunk_index) — citation `[N]` từ ASK Phase 7 ổn định.

---

## Quyết định gate

- ✅ **5/5 AC PASS** → M2a EXIT GATE PASS → tiếp tục Phase 5+ (M2b).
- ⚠️ **3-4/5 PASS** → fix gap, re-run demo trước khi gate. KHÔNG pivot — fix forward.
- ❌ **≤ 2/5 PASS** → Trigger E1 EXIT (PROJECT.md): mở `/gsd-discuss-milestone` re-evaluate. KHÔNG tự pivot.

**Reject demo** = STOP M2b. Operator confirm bằng "reject" với reason cụ thể (which AC failed + symptoms).

⚠️ **Cảnh báo bảo mật:** KHÔNG screenshot terminal có hash password / JWT token. KHÔNG commit `.env` chứa OPENAI_API_KEY. Đổi password admin Admin@123 trước khi deploy production (Phase 5 USER-02 sẽ implement reset-password endpoint chính thức).

---

## Reference

- `.planning/PROJECT.md` (M2a/M2b split + EXIT criteria E1-E5)
- `.planning/ROADMAP.md` Phase 4 line 140-169 (success criteria)
- `.planning/REQUIREMENTS.md` INGEST-01..08 line 45-52
- `.planning/research/PITFALLS.md` (R1/R4/P8/P13/P14)
- `.planning/CONVENTIONS.md` section 3 (APP_NAMESPACE) + section 2 (naming snake_case)
- `.planning/phases/04-cocoindex-flow-mvp-document-ingest/04-COCOINDEX-API-RESEARCH.md` (cocoindex 1.0.3 actual API + A4 decision rationale)
