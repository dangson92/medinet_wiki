---
phase: 02-docling-service-python-sidecar
plan: 08
subsystem: docling-pipeline
tags: [readme, docs, smoke-verify, deferred-runtime, dsvc, w6]
status: completed
requires:
  - "Plan 02-01 (skeleton + Dockerfile)"
  - "Plan 02-02 (docker-compose.yml root, 4 service)"
  - "Plan 02-06 (FastAPI app + 3 endpoint + lifespan B5)"
  - "Plan 02-07 (pytest suite 6 file: test_health, test_extract, test_ocr, test_table_figure, test_limits, test_logging)"
provides:
  - "docling-pipeline/README.md ~372 dòng — install local + Docker, 9 env vars, 3 endpoint, schema DSVC-02, smoke 5 SC, pytest suite, troubleshoot"
  - "W6 evidence: 2 file dataset Phase 1 (tri_thuc_chinh_tri.pdf + DMD_T1-01_scanned.pdf) đã verify tồn tại trên filesystem trước smoke"
  - "Phase 2 documentation hoàn chỉnh — Phase 3 Go adapter có README đầy đủ để wire qua HTTP contract DSVC-01/02"
affects:
  - "Phase 3 (Go adapter): README đã chốt endpoint signature + status code + schema → adapter Go có thể implement mock + integration test bám sát"
tech_stack_added: []
patterns_used:
  - "README structure 10 mục: tổng quan / kiến trúc ASCII / install / env / endpoint / schema / smoke / pytest / troubleshoot / structure"
  - "Smoke commands explicit reference fixture path (W6) — KHÔNG dùng glob pattern để tránh CI pick file sai"
key_files_created:
  - docling-pipeline/README.md
key_files_modified: []
decisions:
  - "Smoke runtime DEFERRED — Docker daemon (Docker Desktop) không khả dụng trên dev Windows hiện tại; KHÔNG retry vô hạn theo plan note 'có thể defer verify này nếu mạng yếu / Docker không sẵn sàng'"
  - "README giữ tiếng Việt 100% phần giải thích; lệnh shell + tên hàm + tên header HTTP giữ tiếng Anh (theo CLAUDE.md global)"
  - "B1 confirm: KHÔNG claim EXTRACT-05 trong frontmatter requirements (đã move sang Phase 3 trong REQUIREMENTS.md commit 2026-04-28)"
  - "W6 confirm: 2 file dataset đã verify tồn tại qua ls -la — KHÔNG cần fallback pick first .pdf"
metrics:
  duration_minutes: 3
  completed_date: "2026-04-29"
  tasks_completed: 1
  files_created: 1
  files_modified: 0
requirements_addressed:
  - DSVC-01
  - DSVC-02
  - DSVC-03
  - DSVC-04
  - DSVC-05
  - DSVC-06
  - EXTRACT-02
  - EXTRACT-03
  - EXTRACT-04
---

# Phase 2 Plan 08: README + Smoke Verify Summary

**One-liner:** Tạo `docling-pipeline/README.md` (~372 dòng tiếng Việt) — install local + Docker, 9 env vars, 3 endpoint signature, schema DSVC-02 đầy đủ, smoke 5 SC commands explicit reference 2 file dataset Phase 1 (W6), pytest suite 6 file, troubleshoot 7 case. Smoke runtime container DEFERRED vì Docker Desktop không khả dụng trên dev Windows hiện tại — đã ghi rõ 1 lệnh user chạy local để confirm.

## Outcome

- 1 file `docling-pipeline/README.md` ~372 dòng commit ở `ed5515e`.
- Verify automated từ plan PASS:
  - File tồn tại.
  - Chứa "DSVC-02" (schema reference).
  - Chứa "vie+eng" (OCR languages — DSVC-03).
  - Chứa "docker compose build" (run instruction).
  - Chứa "tri_thuc_chinh_tri.pdf" (W6 fixture).
  - Chứa "DMD_T1-01_scanned.pdf" (W6 fixture).
  - Line count 372 ≥ 100 (min_lines threshold).
- W6 verify dataset: 2 file Phase 1 đã ls -la confirm tồn tại trên filesystem (`eval/dataset/sources/tri_thuc_chinh_tri.pdf` 97KB + `eval/dataset/scanned/DMD_T1-01_scanned.pdf` 3.7MB).

## Tasks Completed

| Task | Name                                                                                              | Commit  | Files                       |
| ---- | ------------------------------------------------------------------------------------------------- | ------- | --------------------------- |
| 1    | Tạo `docling-pipeline/README.md` (10 mục, ~372 dòng, W6 explicit dataset path)                    | ed5515e | docling-pipeline/README.md  |
| 2    | Smoke verify (checkpoint:human-verify) — DEFERRED Option B vì Docker daemon không khả dụng        | N/A     | (không file mới)            |

## Smoke Verify Status

**Status: DEFERRED (Option B trong plan)**

Lý do defer: `docker ps` từ executor trả `error during connect: ... open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified` — Docker Desktop không chạy trên dev Windows hiện tại. Plan đã pre-approve defer trong objective:

> "⚠️ Note runtime: Docker build lần đầu có thể tốn 5-10 phút (download Docling models + apt install Tesseract). Executor có thể `runtime_smoke: true` flag — nếu môi trường không Docker, chỉ commit README và defer smoke cho user (mark Phase 2 PARTIAL như Phase 1)."

### Checklist user chạy local sau khi Docker Desktop start

```bash
cd D:/ChuongNV_Medinet/AI/medinet_wiki/Hub_All

# 0. Verify dataset (W6) — ĐÃ XONG, fixture còn tồn tại
ls -la eval/dataset/sources/tri_thuc_chinh_tri.pdf       # 97KB
ls -la eval/dataset/scanned/DMD_T1-01_scanned.pdf        # 3.7MB

# 1. Build container (5-10 phút lần đầu — download Tesseract + Docling)
docker compose build docling-pipeline

# 2. Tạo override để expose port 8001 ra host (KHÔNG commit file này)
cat > docker-compose.override.yml <<'EOF'
services:
  docling-pipeline:
    ports:
      - "8001:8001"
    depends_on: []
EOF

# 3. Start docling only (không cần postgres/chroma cho smoke)
docker compose up -d docling-pipeline
docker compose logs -f docling-pipeline    # Đợi event "models_warmed" state=ready (~30-60s)

# 4. Verify 5 SC
# SC1
curl -f http://localhost:8001/healthz                                                                                       # → 200 {"status":"healthy"}
sleep 60                                                                                                                     # Đợi models warm
curl -f http://localhost:8001/readyz                                                                                        # → 200 {"status":"ready"} (B5 case b/c)

# SC2 — PDF normal (W6 explicit fixture)
curl -X POST http://localhost:8001/v1/process \
  -H "X-Request-Id: smoke-test-pdf-1" \
  -F "file=@eval/dataset/sources/tri_thuc_chinh_tri.pdf" \
  -F "hub_code=test" -F "doc_type=test" \
  -o /tmp/smoke_pdf.json
python -c "import json; d=json.load(open('/tmp/smoke_pdf.json')); assert d['doc_meta']['file_type']=='pdf'; assert len(d['chunks'])>0; print('SC2 PASS:', len(d['chunks']), 'chunks')"

# SC3 — scanned PDF VN OCR (W6 explicit fixture — đảo ngược fail Phase 1 SC4)
curl -X POST http://localhost:8001/v1/process \
  -H "X-Request-Id: smoke-test-scanned-1" \
  -F "file=@eval/dataset/scanned/DMD_T1-01_scanned.pdf" \
  -F "hub_code=test" -F "doc_type=scanned" \
  -o /tmp/smoke_scanned.json
python -c "import json; d=json.load(open('/tmp/smoke_scanned.json')); txt=' '.join(c['text'] for c in d['chunks']).lower(); assert any(t in txt for t in ['đỗ minh','định vị','trung tâm']), 'OCR VN fail'; print('SC3 PASS:', len(d['chunks']), 'chunks, OCR vie OK')"

# SC5 — 413 limit (Windows PowerShell)
# $bytes = New-Object byte[] 62914560; [IO.File]::WriteAllBytes("$env:TEMP\big.pdf", $bytes)
# curl.exe -i -X POST http://localhost:8001/v1/process -F "file=@$env:TEMP\big.pdf"
# Expected: HTTP/1.1 413 Payload Too Large

# 5. Cleanup
docker compose down
rm docker-compose.override.yml /tmp/smoke_pdf.json /tmp/smoke_scanned.json
```

User report kết quả qua issue/PR comment. Nếu fail, paste error log để re-route fix theo Plan 02-08 task 2 resume signal.

## Decisions Made

1. **Smoke runtime DEFERRED — Option B** vì Docker Desktop không chạy. Plan đã pre-approve fallback này trong objective. KHÔNG retry vô hạn theo nguyên tắc "Build Docker container có thể chậm hoặc fail (Windows, Docker Desktop chưa start, etc.) — chấp nhận deviation".
2. **README 10 mục có architecture diagram ASCII** — giúp Phase 3 Go adapter dev hình dung request flow rõ ngay đầu file, không cần đọc CONTEXT.md.
3. **W6 explicit reference 2 file dataset trong README + Summary** — KHÔNG dùng glob pattern (vd `*.pdf`) vì CI/dev khác nhau có thể pick file khác → mất reproducibility smoke result.
4. **README giữ tiếng Việt 100% phần giải thích** — theo CLAUDE.md global. Lệnh shell + tên hàm + HTTP header giữ tiếng Anh.
5. **B1 confirm KHÔNG claim EXTRACT-05** trong frontmatter — đã move sang Phase 3 trong REQUIREMENTS.md commit 2026-04-28 Traceability table.

## Verification Performed

- `test -f docling-pipeline/README.md` → exists.
- `grep -q "DSVC-02" docling-pipeline/README.md` → match.
- `grep -q "vie+eng" docling-pipeline/README.md` → match.
- `grep -q "docker compose build" docling-pipeline/README.md` → match.
- `grep -q "tri_thuc_chinh_tri.pdf" docling-pipeline/README.md` → match.
- `grep -q "DMD_T1-01_scanned.pdf" docling-pipeline/README.md` → match.
- `wc -l docling-pipeline/README.md` → 372 (≥ 100 min_lines threshold).
- `ls -la eval/dataset/sources/tri_thuc_chinh_tri.pdf` → 97KB (W6 fixture confirmed).
- `ls -la eval/dataset/scanned/DMD_T1-01_scanned.pdf` → 3.7MB (W6 fixture confirmed).
- `docker ps` → fail (Docker Desktop chưa start) → smoke runtime defer Option B.
- `git log --oneline -1` → `ed5515e docs(docling-pipeline): README.md + smoke verify (Phase 2 Wave 4) [phase-2 plan-08]` confirmed.

## Deviations from Plan

**1. [Pre-approved deviation — Option B] Smoke runtime container DEFERRED**

- **Found during:** Task 2 (checkpoint:human-verify) precondition check.
- **Issue:** `docker ps` trả `error during connect: ... open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified` — Docker Desktop không khả dụng.
- **Resolution:** Mark Option B (defer cho user) theo plan task 2 fallback. README đã include 1 lệnh user chạy local. Plan executor KHÔNG retry vô hạn theo task spec.
- **Files modified:** Không có.
- **Commit:** N/A.

## Known Stubs

Không có stub. README mô tả chính xác state hiện tại của service (FastAPI app + 3 endpoint + lifespan B5 + structlog + 6 file pytest đã commit ở Plan 06/07). Smoke runtime defer ≠ stub — code đã hoàn chỉnh, chỉ thiếu evidence runtime container thật.

## Threat Flags

Không phát hiện threat surface mới. README chỉ document — không mở endpoint mới, không thêm input boundary.

## TDD Gate Compliance

Plan 02-08 không phải plan TDD (`type: execute`, không có `tdd="true"` trong tasks). Task 1 chỉ là docs.

## Next Step

- **Phase 2 PARTIAL — code 100% complete, smoke runtime defer cho user.** Tương tự Phase 1 closure pattern.
- User chạy 1 lệnh `docker compose build docling-pipeline && docker compose up -d docling-pipeline && curl http://localhost:8001/healthz` (chi tiết trong README mục 6 + Summary này) sau khi Docker Desktop start. Report kết quả → mark Phase 2 COMPLETE hoặc re-route fix nếu smoke fail.
- **Phase 3 (Go adapter `DoclingExtractor`) sẵn sàng start** — contract DSVC-01 + DSVC-02 đã chốt qua Plan 02-06 + README Plan 02-08. Phase 3 có thể dùng mock JSON response cho unit test ngay; integration test cuối Phase 3 đợi user xác nhận smoke Phase 2 pass.

## Self-Check: PASSED

- File `docling-pipeline/README.md` → FOUND (372 dòng).
- Commit `ed5515e` → FOUND in `git log` (`docs(docling-pipeline): README.md + smoke verify (Phase 2 Wave 4) [phase-2 plan-08]`).
- 2 file dataset W6 fixture (`tri_thuc_chinh_tri.pdf` + `DMD_T1-01_scanned.pdf`) → FOUND on filesystem.
- Verify regex từ plan (DSVC-02, vie+eng, docker compose build, 2 file dataset, line count) → ALL PASS.
- Smoke runtime defer Option B đúng theo plan pre-approval (Docker Desktop không khả dụng).
