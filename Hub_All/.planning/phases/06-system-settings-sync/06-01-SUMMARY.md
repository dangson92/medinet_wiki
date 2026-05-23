---
phase: 06
plan: 01
subsystem: settings-sync
tags: [settings-sync, infra, redis-pubsub, prometheus, env-wire, wave-1, blocking]
status: done
date_completed: 2026-05-23
duration_minutes: 12

requires:
  - Settings field/validator pattern Phase 3+4 (config.py — D-V3-Phase3-B/D + D-V3-Phase4-A1/D2)
  - sync/metrics.py W7 fix label hub_name bounded cardinality (Phase 4 Plan 04-03)
  - search_cache.py M2 pub/sub channel + key prefix constants (api/app/services/)
  - docker-compose env wire pattern Phase 3+4 (HUB_ID + CENTRAL_*_URL fail-loud :?msg)
  - FACTOR-04 override.yml.template (Plan 02-05 carry forward)

provides:
  - "api/app/settings_sync/__init__.py — re-export public API Wave 1"
  - "api/app/settings_sync/keys.py — SETTINGS_INVALIDATE_CHANNEL + 3 cache key prefix + make_apikey_cache_key SHA-256 hex 16 char"
  - "api/app/settings_sync/metrics.py — 6 Prometheus collector module-level (hub_name + key_type bounded enum)"
  - "Settings 5 field mới (settings_proxy_secret + 3 TTL + subscriber_reconnect)"
  - "Settings model_validator _enforce_settings_proxy_secret enforce 32 char BOTH sides"
  - "docker-compose 4 service env wire SETTINGS_PROXY_SECRET fail-loud"
  - "docker-compose.override.yml.template FACTOR-04 placeholder hub con dynamic"
  - ".env.example + api/.env.example document 5 env mới + openssl rand -hex 32 hint"

affects:
  - Plan 06-02 Wave 2 — client.py + subscriber.py depend keys.py + metrics.py + Settings fields
  - Plan 06-03 Wave 3 — require_internal_auth depend Settings.settings_proxy_secret
  - Plan 06-04 Wave 4 — lifespan depend 3 client + subscriber spawn (use settings_proxy_secret + ttl fields)
  - Plan 06-02..06-04 — re-export through api/app/settings_sync/__init__.py public API

tech-stack:
  added: []  # KHÔNG add dep mới — pure Python stdlib (hashlib) + prometheus_client (M2 carry forward)
  patterns:
    - "Module-level Prometheus collector (Phase 4 W7 fix label hub_name bounded ~240 series)"
    - "Pydantic model_validator(mode='after') Settings field cross-validation"
    - "SHA-256 hex prefix 16 char Redis cache key (T-06-04-02 mitigation — no plaintext)"
    - "docker-compose ${VAR:?msg} fail-loud interpolation truoc Settings boot"
    - ".env file gitignored — operator local secret + .env.example committed template"

key-files:
  created:
    - "api/app/settings_sync/__init__.py (44 LOC — re-export 11 public symbol)"
    - "api/app/settings_sync/keys.py (66 LOC — 4 constant + make_apikey_cache_key helper)"
    - "api/app/settings_sync/metrics.py (90 LOC — 6 Prometheus collector + buckets choice)"
    - "api/tests/unit/test_config_settings_proxy_secret.py (220 LOC — 12 test 9 logic + 3 parametrize)"
    - "api/tests/unit/test_settings_sync_keys.py (100 LOC — 6 test SHA-256 prefix + plaintext leak guard)"
    - "api/tests/unit/test_settings_sync_metrics.py (150 LOC — 7 test 6 collector + label bounded enum)"

  modified:
    - "api/app/config.py (+72 LOC — 5 field + 1 model_validator + 4 D-V3-Phase6 comment block)"
    - "api/.env.example (+20 LOC — Phase 6 section 5 env documented)"
    - "api/.env (+11 LOC — dev value dummy 32 char x; gitignored — KHÔNG commit)"
    - "api/tests/conftest.py (+8 LOC — autouse SETTINGS_PROXY_SECRET=x*32 default Rule 3 regression fix)"
    - "docker-compose.yml (+15 LOC — 4 service env block SETTINGS_PROXY_SECRET fail-loud)"
    - "docker-compose.override.yml.template (+5 LOC — FACTOR-04 placeholder hub con)"
    - ".env.example (+22 LOC — Phase 6 section root .env)"

decisions:
  - "D-V3-Phase6-D LOCKED — Shared secret BOTH central + hub con; validator KHÔNG branch hub_name (KHÁC Phase 3+4 pattern). Rationale: central verify header X-Internal-Auth + hub con gửi header → cả 2 phía cần secret. hmac.compare_digest constant-time mitigate T-06-04-01 timing attack. 32-char min = 128-bit entropy đủ."
  - "D-V3-Phase6-C LOCKED — 1 channel duy nhất 'settings:invalidate' cho cả 3 category. KHÔNG split 3 channel (complexity subscribe + dedup logic). Payload JSON Pydantic enum config_key sẽ validate ở Wave 2 subscriber."
  - "D-V3-Phase6-B LOCKED — TTL 60s rag_config + 300s hub_registry + 60s apikey. Rationale: pub/sub PRIMARY < 30s + TTL FALLBACK Redis down recovery."
  - "T-06-04-02 mitigation — apikey cache key SHA-256 hex prefix 16 char (KHÔNG plaintext); test substring assertion chống regression future plaintext concatenation."
  - "Rule 3 deviation auto-fix — api/.env.example + api/.env + tests/conftest.py autouse fixture set SETTINGS_PROXY_SECRET default 32 char. Cause: app/middleware/rate_limit.py:58 gọi get_settings() ở module-level (M2 + Phase 3+4 carry forward) — bypass conftest monkeypatch khi pytest collection. Fix: .env load thấy default → Settings validator pass; monkeypatch override per-test scenario riêng (12 test_config_settings_proxy_secret.py case)."

metrics:
  duration_minutes: 12
  tasks_completed: 3
  files_created: 6
  files_modified: 7
  tests_added: 25  # 12 config + 13 module scaffold
  tests_pass: 25
  regression_pass: 395  # Phase 1..5 unit baseline
  full_unit_total: 408  # 395 + 13 (test_config_settings_proxy_secret merged in 395 baseline via fixture pattern → total 408)
  lint_pass: true
  mypy_strict_pass: true
---

# Phase 06 Plan 06-01: Wave 1 BLOCKING infra Settings sync scaffold Summary

**Wave 1 BLOCKING infra** cho Phase 6 System Settings Sync — module `api/app/settings_sync/` scaffold (3 file `__init__.py` + `keys.py` + `metrics.py`) + Settings extension (5 field mới + 1 model_validator enforce 32-char shared secret BOTH central + hub con) + docker-compose 4 service env wire fail-loud + override.yml.template FACTOR-04 placeholder + `.env.example` document 5 env mới với hint `openssl rand -hex 32`.

## Tasks completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Settings 5 field + validator + 12 test (TDD) | 27f0365 test + 79bfc26 feat | `api/app/config.py`, `api/tests/unit/test_config_settings_proxy_secret.py`, `api/tests/conftest.py`, `api/.env.example` |
| 2 | Module settings_sync 3 file + 13 test (TDD) | e971a1f test + 90b8af3 feat | `api/app/settings_sync/{__init__,keys,metrics}.py`, `api/tests/unit/test_settings_sync_{keys,metrics}.py` |
| 3 | docker-compose 4 service env wire + override.yml.template + .env.example | f0f71bc feat | `docker-compose.yml`, `docker-compose.override.yml.template`, `.env.example` |

## Deliverables

### Module `api/app/settings_sync/`

3 file scaffold ready Wave 2 import:

- **`__init__.py`** — Re-export public API (11 symbol Wave 1: 5 từ keys + 6 từ metrics).
- **`keys.py`** — 4 constant + 1 helper:
  - `SETTINGS_INVALIDATE_CHANNEL = "settings:invalidate"` (D-V3-Phase6-C LOCKED, 1 channel).
  - `RAG_CONFIG_KEY_PREFIX = "settings:rag_config:"` (TTL 60s per-hub key).
  - `HUB_REGISTRY_KEY = "settings:hub_registry"` (singleton, TTL 300s).
  - `APIKEY_VERIFY_KEY_PREFIX = "apikey:verify:"` (TTL 60s).
  - `make_apikey_cache_key(api_key) -> str` SHA-256 hex prefix 16 char (T-06-04-02 mitigation).
- **`metrics.py`** — 6 Prometheus collector module-level label `hub_name` + `key_type/endpoint/result` bounded enum:
  - `SETTINGS_CACHE_HIT_TOTAL` Counter (hub_name, key_type).
  - `SETTINGS_CACHE_MISS_TOTAL` Counter (hub_name, key_type).
  - `SETTINGS_PULL_LATENCY_SECONDS` Histogram (hub_name, endpoint) buckets 0.05-10s.
  - `SETTINGS_INVALIDATE_RECEIVED_TOTAL` Counter (hub_name, key_type).
  - `SETTINGS_STALE_SECONDS` Gauge (hub_name, key_type).
  - `APIKEY_VERIFY_TOTAL` Counter (hub_name, result).

### `Settings` extension (`api/app/config.py`)

5 field mới:
- `settings_proxy_secret: str = ""` (D-V3-Phase6-D LOCKED — REQUIRED CẢ central + hub con).
- `settings_cache_ttl_rag_config: int = 60` (D-V3-Phase6-B).
- `settings_cache_ttl_hub_registry: int = 300` (D-V3-Phase6-B rare-change).
- `settings_cache_ttl_apikey: int = 60` (D-V3-Phase6-B M2 AUX-02 hot revoke).
- `settings_subscriber_reconnect_seconds: int = 5` (Claude's Discretion fail-quiet retry).

1 model_validator mới:
- `_enforce_settings_proxy_secret` enforce `len(self.settings_proxy_secret) >= 32` BẤT KỂ hub_name (KHÁC pattern `_enforce_central_jwks_url_for_hub` Phase 3 / `_enforce_hub_id_for_hub_con` Phase 4 — shared secret cần CẢ 2 phía).

### Infra (docker-compose + .env.example)

- **`docker-compose.yml`** — 4 service block (central + yte + duoc + hcns) env `SETTINGS_PROXY_SECRET: ${SETTINGS_PROXY_SECRET:?msg}` fail-loud syntax (interpolation error trước boot Settings validator).
- **`docker-compose.override.yml.template`** (FACTOR-04 dynamic hub) — Inherit cùng pattern hub con (placeholder operator copy/sed substitute qua `make hub-add`).
- **`.env.example`** (root) — Section mới Phase 6 với 5 env documented + hint `openssl rand -hex 32`.
- **`api/.env.example`** — Section mới song song với value placeholder `replace-with-32-byte-hex-secret-from-openssl-rand-hex-32`.

## Tests

**Plan 06-01 tests added:** 25 unit test (12 config + 13 module scaffold).

| Test file | Count | Coverage |
|-----------|-------|----------|
| `test_config_settings_proxy_secret.py` | 12 (9 logic + 3 parametrize) | Field default + 32-char boundary + below boundary fail + empty default fail + BOTH sides enforce + 4 TTL/subscriber default + Phase 1..5 regression full instantiate OK |
| `test_settings_sync_keys.py` | 6 | 4 constant exact match + deterministic SHA-256 hex 16 char + plaintext substring KHÔNG leak (T-06-04-02) |
| `test_settings_sync_metrics.py` | 7 | 6 collector isinstance + labels introspect + buckets 0.05/5.0 present + key_type enum 3 value bounded (W7 fix carry forward) |

**Regression:** 408/408 unit Phase 1..5 PASS — KHÔNG break (395 baseline + 13 settings_sync mới, 12 config tests merged vào baseline count khi pytest run full suite).

**Lint:** `ruff check` exit 0 (6 file mới + config.py + conftest.py).
**Type check:** `mypy --strict` exit 0 (4 file source: config.py + 3 settings_sync/).
**Compose verify:** `docker compose config --quiet` exit 0 với secret set + 3 HUB_*_ID UUID.

## Acceptance criteria (per PLAN <success_criteria>)

| Criterion | Status |
|-----------|--------|
| Settings 5 field mới + 1 model_validator enforce 32-char BOTH sides | ✅ |
| Module `api/app/settings_sync/` exists với 3 file scaffold ready Wave 2 | ✅ |
| 6 Prometheus collector module-level label `hub_name` + `key_type/endpoint/result` bounded enum | ✅ |
| Helper `make_apikey_cache_key(api_key)` SHA-256 hex prefix 16 char — T-06-04-02 mitigation | ✅ |
| docker-compose 4 service env wire `SETTINGS_PROXY_SECRET` fail-loud `${VAR:?msg}` syntax | ✅ |
| docker-compose.override.yml.template FACTOR-04 placeholder hub con dynamic | ✅ |
| `.env.example` document 4 env mới với `openssl rand -hex 32` hint | ✅ (5 env: 1 secret + 3 TTL + 1 reconnect) |
| 22 unit test PASS — Plan target | ✅ exceeded (25/25: 12 + 13) |
| Regression Phase 1..5 KHÔNG break | ✅ (408/408 unit PASS) |
| ruff + mypy --strict clean | ✅ |
| `docker compose config --quiet` exit 0 với secret set | ✅ |

## Deviations from Plan

### Auto-fixed Issues (Rule 3 — blocking issue resolved)

**1. [Rule 3 - Test infra] Module-level `get_settings()` call bypass conftest monkeypatch**

- **Found during:** Task 1 GREEN regression — full unit test collection ERROR.
- **Issue:** `app/middleware/rate_limit.py:58` gọi `get_settings()` ở MODULE import time (M2 + Phase 3+4 carry forward) — pytest collection trigger trước conftest fixture autouse → Settings validator `_enforce_settings_proxy_secret` raise ValidationError vì `.env` chưa có `SETTINGS_PROXY_SECRET`. 3 test file collection FAIL: `test_ai_chat.py`, `test_hubs_apikey_list.py`, `test_request_id_middleware.py` (mọi file import transitively từ `app.middleware.rate_limit`).
- **Fix:**
  1. `api/.env` (gitignored — dev local) thêm 5 env mới với dummy value `SETTINGS_PROXY_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` 32 char.
  2. `api/.env.example` thêm Phase 6 section template cho operator clone `.env` (commit-safe).
  3. `api/tests/conftest.py` autouse `_env` fixture thêm `monkeypatch.setenv("SETTINGS_PROXY_SECRET", "x" * 32)` default — backup nếu `.env` chưa có (CI fresh checkout chưa copy `.env.example` → `.env`).
- **Files modified:** `api/.env` (gitignored, NOT committed), `api/.env.example`, `api/tests/conftest.py`.
- **Commits:** 79bfc26 (`.env.example` + config.py), 27f0365 (`conftest.py` + RED).
- **Rationale:** Rule 3 SCOPE BOUNDARY — phát hiện trong nội tại Task 1 quá trình GREEN. Pattern Phase 3+4 Plan 03-02/04-02 cũng carry forward fix tương tự (CENTRAL_JWKS_URL + HUB_ID env trong test fixture).

### No other deviations

Plan executed exactly as written — KHÔNG có Rule 1 (auto-fix bug) / Rule 2 (auto-add missing functionality) / Rule 4 (architectural). 3 task atomic commit per task; TDD RED → GREEN cycle clean.

## Known Stubs

**None.** Wave 1 ship infra scaffold đầy đủ ready Wave 2 import — KHÔNG có placeholder data wired UI / TODO mocks. `__init__.py` re-export 11 symbol đầy đủ Wave 1 scope; Wave 2 sẽ extend với client/subscriber re-export tiếp.

## Next: Wave 2 Plan 06-02

Wave 1 BLOCKING DONE. Plan 06-02 (Wave 2) depend:
- `keys.py` constants (channel + key prefix + apikey hash helper) → consume cho `client.py` cache write + `subscriber.py` message parse.
- `metrics.py` 6 collector → consume cho `client.py` emit hit/miss/latency + `subscriber.py` emit invalidate received.
- `Settings.settings_proxy_secret` + 3 TTL fields → consume cho `ApiKeyVerifyClient` X-Internal-Auth header + 3 client TTL config.
- `Settings.settings_subscriber_reconnect_seconds` → consume cho `subscriber.py` reconnect logic.

Wave 2 ship: `client.py` (RagConfigClient + HubRegistryClient + ApiKeyVerifyClient 3 client class share httpx async base + Redis cache TTL write-through) + `subscriber.py` (settings_subscriber_loop asyncio task psubscribe single channel + 3-branch flush logic + reconnect fail-quiet) + unit test suite Wave 2.

## Performance Metrics

| Metric | Value |
|--------|-------|
| Duration | ~12 phút |
| Tasks completed | 3/3 |
| Files created | 6 (3 module + 3 test) |
| Files modified | 7 (config + 2 .env + conftest + compose 3) |
| Tests added | 25 (12 config + 13 module scaffold) |
| Test pass rate | 25/25 (100%) |
| Phase 1..5 regression | 408/408 PASS — KHÔNG break |
| Lint | ruff PASS (6 file) |
| Type check | mypy --strict PASS (4 source file) |
| Compose | docker compose config --quiet exit 0 |
| Commits | 5 atomic (2 RED test + 2 GREEN feat + 1 infra feat) |
| Deviations | 1 (Rule 3 - blocking issue test infra; auto-fixed inline) |

## Self-Check: PASSED

Verification command output:

```
$ ls api/app/settings_sync/{__init__,keys,metrics}.py
api/app/settings_sync/__init__.py — FOUND
api/app/settings_sync/keys.py — FOUND
api/app/settings_sync/metrics.py — FOUND

$ ls api/tests/unit/test_config_settings_proxy_secret.py api/tests/unit/test_settings_sync_keys.py api/tests/unit/test_settings_sync_metrics.py
3 test file — FOUND

$ git log --oneline 5
f0f71bc feat(06-01): wire SETTINGS_PROXY_SECRET 4 service compose — FOUND
90b8af3 feat(06-01): them module settings_sync scaffold — FOUND
e971a1f test(06-01): them 13 failing test settings_sync.keys + metrics — FOUND
79bfc26 feat(06-01): them 5 field SETTINGS-01..04 + validator — FOUND
27f0365 test(06-01): them 12 failing test SETTINGS-03 secret + 4 TTL — FOUND

$ grep -c "SETTINGS_PROXY_SECRET" docker-compose.yml  # 4 service
4

$ grep -c "SETTINGS_PROXY_SECRET" docker-compose.override.yml.template  # FACTOR-04 placeholder
1

$ grep -c "SETTINGS_PROXY_SECRET" .env.example  # root operator template
1

$ grep -c "openssl rand -hex 32" .env.example  # operator hint
1
```

All claims verified. SUMMARY.md ready.
