---
phase: 5
plan: 01
subsystem: reverse-proxy
tags: [caddy, reverse-proxy, env, docker-compose, v3.0, phase5, wave1]
requirements: [PROXY-01]
wave: 1
status: DONE
date: 2026-05-23
dependency_graph:
  requires: []
  provides:
    - "Caddyfile wiki server block với @hub_api path_regexp + handle_path strip + central /api/* + .well-known + static SPA fallback"
    - "docker-compose caddy service env WIKI_PUBLIC_DOMAIN + HUBS_ALLOWLIST_REGEX + frontend/dist volume mount + depends_on python-api-central"
    - ".env.example operator setup 3 env mới"
  affects:
    - "Plan 05-02 (FE prefix detect): tiêu thụ HUBS_ALLOWLIST_REGEX qua window.__HUB_CONFIG__ fallback hardcode + Caddy serve dist/"
    - "Plan 05-03 (branding): tiêu thụ Caddy file_server serve /branding/<hub>/logo.svg từ public/"
    - "Plan 05-05 (hub-add.sh extend): tiêu thụ HUBS_ALLOWLIST + HUBS_ALLOWLIST_REGEX update + caddy reload"
    - "Plan 05-06 (closeout smoke): kiểm tra `curl https://localhost/<hub>/api/health` PASS sau khi build frontend + docker compose up"
tech-stack:
  added: []
  patterns:
    - "Caddy single Caddyfile + env-driven regex (D-V3-Phase5-A1 LOCKED)"
    - "path_regexp + route + uri strip_prefix (D-V3-Phase5-A2 LOCKED — KHÔNG handle_path glob vì cần placeholder)"
    - "WIKI_PUBLIC_DOMAIN env song song MCP_PUBLIC_DOMAIN (D-V3-Phase5-A4 — carry forward M2 Phase 8.3 pattern)"
key-files:
  created: []
  modified:
    - "Hub_All/Caddyfile (+67 lines wiki block sau MCP block)"
    - "Hub_All/docker-compose.yml (+11 lines caddy service: 2 env + 1 volume mount + 1 depends_on)"
    - "Hub_All/.env.example (+19 lines section reverse proxy + 3 env documented VN comment)"
decisions:
  - "D-V3-Phase5-A1 LOCKED implement: 1 Caddyfile + env-driven HUBS_ALLOWLIST_REGEX (KHÔNG fragment per-hub)"
  - "D-V3-Phase5-A2 LOCKED implement: route block + uri strip_prefix /{re.hub_api.1} (KHÔNG handle_path glob)"
  - "D-V3-Phase5-A4 LOCKED implement: WIKI_PUBLIC_DOMAIN env carry forward MCP_PUBLIC_DOMAIN pattern"
  - "Deviation Rule 1: Bỏ scheme `http://` khỏi dynamic upstream `reverse_proxy python-api-{re.hub_api.1}:8080` (Caddy CẤM placeholder khi address có scheme — Pitfall 1 documented 05-RESEARCH §Common Pitfalls)"
metrics:
  duration_min: 15
  tasks_completed: "3/3"
  files_modified: 3
  commits: 3
  insertions: 97
  deletions: 0
---

# Phase 5 Plan 01: Reverse Proxy Scaffolding Summary

**One-liner:** Mở rộng Caddyfile thêm wiki server block subpath routing đa hub (`{$WIKI_PUBLIC_DOMAIN}` + `@hub_api path_regexp` + `route { uri strip_prefix }` + central /api/* + .well-known + SPA fallback) song song MCP block hiện hữu; wire `WIKI_PUBLIC_DOMAIN` + `HUBS_ALLOWLIST_REGEX` env + `./frontend/dist:/srv/wiki/dist:ro` volume vào caddy service; document 3 env mới ở `.env.example` — Wave 1 BLOCKING xong, sẵn sàng cho Wave 2 Plan 05-02 (FE prefix detect) + 05-03 (branding registry).

## Objective

Wave 1 BLOCKING Caddy reverse proxy scaffolding cho `wiki.domain.com/<hub>` subpath routing đa hub (PROXY-01). 3 file modified atomic 3 commit — sẵn sàng cho Wave 2 (Plan 05-02 + 05-03 parallel) và Wave 4 (Plan 05-05 hub-add reload).

Carry forward M2 Phase 8.3 MCP block KHÔNG đụng — wiki block đứng SONG SONG (verified `grep -c "{$MCP_PUBLIC_DOMAIN}" Caddyfile` = 1 ban đầu, sau commit Task 1 vẫn = 1 ở line 14).

## Tasks Done

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Mở rộng Caddyfile thêm `{$WIKI_PUBLIC_DOMAIN}` server block (PROXY-01 + D-V3-Phase5-A1/A2/A4) | `08accd1` | `Hub_All/Caddyfile` (+67) |
| 2 | Sửa docker-compose.yml caddy service inject env mới + frontend/dist mount (PROXY-01 + D-V3-Phase5-A4) | `9e4c43a` | `Hub_All/docker-compose.yml` (+11) |
| 3 | Cập nhật `.env.example` document 3 env mới (PROXY-01 operator setup) | `f71dbfe` | `Hub_All/.env.example` (+19) |

## Acceptance Criteria

| # | Criterion | Verify | Status |
|---|-----------|--------|--------|
| 1 | `grep -q "path_regexp hub_api" Caddyfile` | Line 32: `@hub_api path_regexp hub_api ^/(...)/api/(.*)$` | PASS |
| 2 | `grep -q "uri strip_prefix /{re.hub_api.1}" Caddyfile` | Line 38 | PASS |
| 3 | `grep -q "reverse_proxy python-api-{re.hub_api.1}:8080" Caddyfile` (KHÔNG `http://` scheme — deviation Rule 1) | Line 42 | PASS (adjusted) |
| 4 | `grep -q "handle /api/\*" Caddyfile` (central API) | Line 55 | PASS |
| 5 | `grep -q "handle /.well-known/\*" Caddyfile` (JWKS Phase 3) | Line 68 | PASS |
| 6 | `grep -q "try_files {path} /index.html" Caddyfile` (SPA fallback) | Line 77 | PASS |
| 7 | `grep -q "X-Forwarded-Hub {re.hub_api.1}" Caddyfile` (debug header) | Line 47 | PASS |
| 8 | `grep -q "{$WIKI_PUBLIC_DOMAIN:localhost}" Caddyfile` (env-driven) | Line 28 | PASS |
| 9 | MCP block UNCHANGED: `grep -c "{$MCP_PUBLIC_DOMAIN}" Caddyfile` = 1 | Line 14 only | PASS |
| 10 | `docker run --rm caddy:2-alpine caddy validate` exit 0 | `Valid configuration` (2 warning non-fatal) | PASS |
| 11 | `docker compose config --quiet` exit 0 (với Phase 4 env set tạm) | exit 0 | PASS |
| 12 | `docker compose config --services` render 8 service | caddy + mcp_service + postgres + 4 python-api-* + redis | PASS |
| 13 | caddy service có `WIKI_PUBLIC_DOMAIN` env | Line 279 trong block 271-297 | PASS |
| 14 | caddy service có `HUBS_ALLOWLIST_REGEX` env | Line 282 | PASS |
| 15 | caddy service có `./frontend/dist:/srv/wiki/dist:ro` volume | Line 292 | PASS |
| 16 | caddy service `depends_on: python-api-central` | Line 296 | PASS |
| 17 | MCP env giữ nguyên: `MCP_PUBLIC_DOMAIN: ${MCP_PUBLIC_DOMAIN` | Line 276 | PASS |
| 18 | `docker compose config | grep -E "WIKI_PUBLIC_DOMAIN|HUBS_ALLOWLIST_REGEX"` returns 2 dòng + `/srv/wiki/dist` | 3 dòng resolved | PASS |
| 19 | `grep -q "^WIKI_PUBLIC_DOMAIN=localhost$" .env.example` | Line 23 | PASS |
| 20 | `grep -q "^HUBS_ALLOWLIST=yte,duoc,hcns$" .env.example` | Line 28 | PASS |
| 21 | `grep -q "^HUBS_ALLOWLIST_REGEX=yte|duoc|hcns$" .env.example` | Line 33 | PASS |
| 22 | Section header VN `Reverse proxy + multi-hub routing (Phase 5 v3.0 — PROXY-01)` | Line 16 | PASS |
| 23 | `wiki.medinet.vn` prod hint comment | Line 22 | PASS |
| 24 | Original env preserved: `POSTGRES_PASSWORD` + `APP_ENV` | Line 10 + 13 | PASS |

**Tổng: 24/24 acceptance criteria PASS.**

## Verification Results

### Caddy validate

```bash
$ MSYS_NO_PATHCONV=1 docker run --rm \
    -e MCP_PUBLIC_DOMAIN=mcp.localhost \
    -e WIKI_PUBLIC_DOMAIN=localhost \
    -e HUBS_ALLOWLIST_REGEX="yte|duoc|hcns" \
    -v "$(pwd -W)/Caddyfile":/etc/caddy/Caddyfile:ro \
    caddy:2-alpine caddy validate --config /etc/caddy/Caddyfile
{"level":"info","msg":"using config from file","file":"/etc/caddy/Caddyfile"}
{"level":"warn","logger":"caddyfile","msg":"Unnecessary header_up X-Forwarded-For: ..."}
{"level":"warn","logger":"caddyfile","msg":"Unnecessary header_up X-Forwarded-Proto: ..."}
{"level":"info","msg":"adapted config to JSON","adapter":"caddyfile"}
{"level":"info","logger":"http.auto_https","msg":"server is listening only on the HTTPS port..."}
Valid configuration
```

Exit 0 + `Valid configuration` literal output. 2 warning `Unnecessary header_up X-Forwarded-For/Proto` (Caddy default behavior đã forward 2 header này — explicit `header_up` thừa nhưng KHÔNG sai). Giữ lại để tường minh + đồng nhất pattern với `X-Forwarded-Hub` custom + `Host` + `X-Real-IP`.

### docker compose config

```bash
$ HUB_YTE_ID=00000000-0000-0000-0000-000000000001 \
  HUB_DUOC_ID=00000000-0000-0000-0000-000000000002 \
  HUB_HCNS_ID=00000000-0000-0000-0000-000000000003 \
  CENTRAL_SYNC_DSN=postgresql://medinet:medinet_dev_pwd@medinet-postgres:5432/medinet_central \
  docker compose config --quiet
$ echo $?
0

$ docker compose config --services | sort
caddy
mcp_service
postgres
python-api-central
python-api-duoc
python-api-hcns
python-api-yte
redis

$ docker compose config | grep -E "WIKI_PUBLIC_DOMAIN|HUBS_ALLOWLIST_REGEX|/srv/wiki/dist"
      HUBS_ALLOWLIST_REGEX: yte|duoc|hcns
      WIKI_PUBLIC_DOMAIN: localhost
        target: /srv/wiki/dist
```

Exit 0; 8/8 service render; 3 dòng env + volume resolve đúng giá trị default từ docker-compose.yml.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug fix] Caddy CẤM placeholder trong dynamic upstream khi address có scheme**

- **Found during:** Task 1 first `caddy validate` attempt
- **Error literal:** `parsing upstream 'http://python-api-{http.regexp.hub_api.1}:8080': due to parsing difficulties, placeholders are not allowed when an upstream address contains a scheme, at /etc/caddy/Caddyfile:39`
- **Pitfall reference:** `.planning/phases/05-reverse-proxy-frontend-subpath/05-RESEARCH.md` §"Common Pitfalls" Pitfall 1 đã document chính xác risk này — placeholder upstream port không support, fallback bỏ scheme `http://` (Caddy default HTTP cho non-TLS upstream). Static upstream (central) giữ nguyên `http://python-api-central:8080` (không placeholder, scheme OK).
- **Fix:** Đổi `reverse_proxy http://python-api-{re.hub_api.1}:8080 { ... }` → `reverse_proxy python-api-{re.hub_api.1}:8080 { ... }` (bỏ `http://` prefix). Caddy default HTTP, port 8080 static; behavior request KHÔNG đổi.
- **Files modified:** `Hub_All/Caddyfile` (1 dòng dynamic upstream — line 42 sau edit)
- **Commit:** `08accd1` (Task 1 với fix inline + comment giải thích Pitfall 1 reference)

Lưu ý: acceptance criterion gốc plan viết `grep -q "reverse_proxy http://python-api-{re.hub_api.1}:8080"` — adjust thành `grep -q "reverse_proxy python-api-{re.hub_api.1}:8080"` (bỏ `http://`) cho match thực tế (đã verified PASS).

### Other

**KHÔNG có deviation Rule 2 / Rule 3 / Rule 4.** Plan executed exactly như written ngoài fix Rule 1 trên (đã anticipate trong 05-RESEARCH Pitfall 1).

## Authentication Gates

KHÔNG có. Plan 05-01 hoàn toàn local file edit + Caddy validate (offline, không cần auth).

## Threat Mitigation Status

| Threat ID | Status | Implementation |
|-----------|--------|----------------|
| T-5-01 (Caddy open redirect / path traversal) | mitigated | `@hub_api path_regexp ^/({...})/api/(.*)$` anchor `^` + `/` cuối → unknown hub fall through to static `handle {}` catch-all (file_server), KHÔNG forward arbitrary upstream |
| T-5-06 (XSS via theme color) | N/A | Caddyfile KHÔNG ảnh hưởng — themeColor hardcoded TS const Plan 05-03 |
| T-5-09 (Spoofing X-Forwarded-Hub) | mitigated | `header_up X-Forwarded-Hub {re.hub_api.1}` Caddy hardcode set từ regex capture — client KHÔNG control |
| T-5-10 (Info disclosure log) | accept | `format json` log path + method + status (KHÔNG body); defer Phase 6 SETTINGS observability PII redaction review |
| T-5-11 (DoS port 80/443) | accept | Caddy default rate limit absent — defer Phase 7 MIGRATE-04 Cloudflare proxy edge tier; LAN dev OK |

## Next Plan Handoff

- **Plan 05-02 (FE prefix detect + vitest Wave 0):** Có thể start Wave 2 parallel với 05-03. Sẽ tiêu thụ `HUBS_ALLOWLIST_REGEX` qua `window.__HUB_CONFIG__` runtime injection (defer Phase 6 SETTINGS-04) HOẶC fallback hardcode `['yte', 'duoc', 'hcns']` (Phase 5 initial). Vite build output `./frontend/dist/` đã được Caddy serve qua volume mount Task 2.
- **Plan 05-03 (branding registry):** Có thể start Wave 2 parallel với 05-02. Sẽ tạo `frontend/src/branding/<hub>/index.ts` × 4 hub + `frontend/public/branding/<hub>/logo.svg` × 4 hub. Caddy serve `/branding/<hub>/logo.svg` qua `file_server` từ `/srv/wiki/dist` (đã wire Task 2).
- **Plan 05-04 (Login + Layout + crossHub + tryRefresh wire):** Wave 3 depend 05-02 + 05-03.
- **Plan 05-05 (hub-add.sh extend FACTOR-04):** Wave 4 depend 05-01 (file `Hub_All/Caddyfile` + `.env.example` từ Plan này). Sẽ append step 8 sed-edit `HUBS_ALLOWLIST` + `HUBS_ALLOWLIST_REGEX` (`tr ',' '|'` transform) + step 9 `docker compose exec caddy caddy reload`.
- **Plan 05-06 (closeout smoke checkpoint runtime):** Wave 5 — sau khi build frontend + docker compose up sẽ smoke `curl https://localhost/yte/api/health` + manual 11 trang React COMPAT-01 smoke regression (R-V3-2 mitigation D-V3-Phase5-D4 LOCKED).

## Risk Carry Forward

- **R-V3-2 HIGH (D6 expire frontend rewrite regress):** Plan 05-01 KHÔNG đụng frontend code (chỉ Caddy + docker-compose + .env). Risk activate khi Plan 05-02 + 05-04 chạy. Smoke regression chốt Plan 05-06 D4 manual checklist 4 hub × 11 trang.

## Self-Check: PASSED

**Created/modified files exist:**
- `Hub_All/Caddyfile`: FOUND (modified, +67 lines, total 87 lines)
- `Hub_All/docker-compose.yml`: FOUND (modified, +11 lines on caddy service block)
- `Hub_All/.env.example`: FOUND (modified, +19 lines section + 3 env)
- `.planning/phases/05-reverse-proxy-frontend-subpath/05-01-SUMMARY.md`: FOUND (this file, just written)

**Commits exist:**
- `08accd1` feat(05-01): Caddyfile wiki block: FOUND in git log
- `9e4c43a` feat(05-01): docker-compose caddy env: FOUND in git log
- `f71dbfe` docs(05-01): .env.example 3 env: FOUND in git log

**Verification commands re-run PASS:**
- `caddy validate` exit 0
- `docker compose config --quiet` exit 0 (với env Phase 4 set tạm)
- 24/24 acceptance grep criteria PASS

---

*Generated: 2026-05-23 sau `/gsd-execute-phase 5` Wave 1 Plan 05-01.*
*Project: MEDWIKI v3.0 Multi-Hub Split — Phase 5 Reverse Proxy + Frontend Subpath.*
