---
status: partial
phase: 06-system-settings-sync
source: [06-VERIFICATION.md]
started: 2026-05-23T08:05:00Z
updated: 2026-05-23T08:05:00Z
defer_to: Phase 7 MIGRATE-05 full E2E
---

## Current Test

[awaiting human testing — defer Phase 7 MIGRATE-05 full E2E golden path per v3.0-b precedent (03-05 + 04-07 + 05-06)]

## Tests

### 1. Smoke runtime full E2E — pub/sub propagate < 30s

expected: Central `PUT /api/rag-config` → 3 hub con (yte/duoc/hcns) subscriber receive `settings:invalidate` event → DEL key `settings:rag_config:<hub>` → lần fetch tiếp theo qua `RagConfigClient.get()` trả config mới trong < 30s (E-V3-4 propagate window).
result: [pending — defer Phase 7]
why_human: Pub/sub propagate timing chỉ verify được khi 4 service runtime đồng thời + real Redis pub/sub thật. `tests/integration/test_settings_sync_pubsub_e2e.py` skip module-level do `fakeredis` async `pubsub.listen()` không yield message reliable; cần Redis live container.

### 2. X-API-Key cache hit round-trip + Prometheus scrape

expected: Lần 1 — hub con nhận `X-API-Key: mdk_...` → `ApiKeyVerifyClient.verify()` cache miss → POST central `/api/api-keys/verify` (X-Internal-Auth header) → 200 valid → setex Redis hash key TTL 60s; lần 2 cùng key → cache hit (KHÔNG HTTP call) + Prometheus `apikey_verify_total{result=cached}` increment +1.
result: [pending — defer Phase 7]
why_human: Cần Redis live + central up + Prometheus scrape verify metric thực sự increment; in-process unit test chỉ mock Redis + httpx.

### 3. Boot fail-loud — central down → hub con uvicorn exit 1

expected: Set `CENTRAL_URL` trỏ host KHÔNG resolve được (ví dụ `http://invalid.local:9999`) → `docker compose up python-api-yte` → log critical `lifespan_settings_sync_init_failed` + container exit code 1 trong 5-10s (KHÔNG silent degrade, R-V3-6 LOW mitigation chain).
result: [pending — defer Phase 7]
why_human: Cần docker daemon + multi-container orchestration + exit code observe; in-process integration test 5 dùng `RagConfigClient.fetch_initial()` direct (KHÔNG asgi_lifespan để tránh leak audit_task).

### 4. Backward incompat — thiếu SETTINGS_PROXY_SECRET → boot fail TRƯỚC lifespan

expected: Operator KHÔNG set `SETTINGS_PROXY_SECRET` trong `.env` → `docker compose up` interpolation error `${VAR:?msg}` exit code 1 TRƯỚC container start (Pydantic Settings validator NOT reached).
result: [pending — defer Phase 7]
why_human: Docker compose interpolation behavior khác giữa version + Docker engine; cần test trên target deploy host.

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps

[None — code-level verification 10/10 PASSED. 4 pending items defer Phase 7 MIGRATE-05 full E2E per v3.0-b precedent.]
