---
title: Gộp MCP subdomain về wiki.medinet.vn/mcp
slug: mcp-subdomain-consolidate
date: 2026-05-23
status: complete
---

# Summary — Gộp `mcp.medinet.vn` về `wiki.medinet.vn/mcp`

## Kết quả

Consolidate MCP service deployment: bỏ subdomain riêng `mcp.medinet.vn` (Phase 8.3 M2 v2.0 carry forward), gộp về subpath `/mcp` cùng domain `wiki.medinet.vn`. Path-prefix mode đã sẵn có ở backend từ M2 — chỉ cần thay đổi reverse proxy + env config.

## Files thay đổi (11)

### Code/config (5)
- `Hub_All/Caddyfile` — Bỏ block `{$MCP_PUBLIC_DOMAIN}`. Block `{$WIKI_PUBLIC_DOMAIN}` thêm Match 3 (OAuth metadata `/.well-known/oauth-authorization-server*` + `oauth-protected-resource*` + `openid-configuration*` → MCP) + Match 5 (`/mcp` exact + `/mcp/*` children → MCP). Match 4 catch-all `/.well-known/*` → central (JWKS) giữ nguyên, Caddy auto-sort prefix dài thắng.
- `Hub_All/docker-compose.yml` — Bỏ env `MCP_PUBLIC_DOMAIN` khỏi caddy service. Comment block cập nhật phản ánh path-prefix consolidation.
- `Hub_All/mcp_service/.env.example` — `MCP_OAUTH_ISSUER_URL=https://mcp.medinet.vn/mcp` → `https://wiki.medinet.vn/mcp` + comment giải thích path suffix khớp `MCP_PATH_PREFIX=mcp`.
- `Hub_All/.env.example` — Comment Phase 5 block: bỏ reference "song song MCP_PUBLIC_DOMAIN", thêm note 2026-05-23 consolidation.
- `Hub_All/mcp_service/README.md` — Section "Reverse proxy + deploy public HTTPS": đổi `MCP_PUBLIC_DOMAIN` → `WIKI_PUBLIC_DOMAIN` + blockquote note path-prefix mode.

### Docs deploy (1)
- `Hub_All/VPS_DEPLOY.md` — 6 chỗ: section 1.4 (2 DNS A → 1), section 3.2 (.env compose bỏ MCP_PUBLIC_DOMAIN), section 3.5 (mcp_service .env issuer URL + thêm MCP_PATH_PREFIX), section 6.1 (dig DNS), section 6.2 (Caddy log + curl healthcheck URL mới `wiki.medinet.vn/.well-known/oauth-authorization-server/mcp`), section 10 (security checklist #13 update issuer URL).

### Planning historical (5 — append "deprecated 2026-05-23" note)
- `Hub_All/.planning/phases/05-reverse-proxy-frontend-subpath/05-CONTEXT.md`
- `Hub_All/.planning/phases/05-reverse-proxy-frontend-subpath/05-RESEARCH.md`
- `Hub_All/.planning/milestones/v2.0-full-rag-rewrite/phases/10-hardening-observability-docs/10-05-SUMMARY.md`
- `Hub_All/.planning/milestones/v2.0-full-rag-rewrite/phases/08.3-mcp-oauth-deploy-public-https/08.3-MCP-AUDIT-2026-05-21.md`
- `Hub_All/.planning/milestones/v2.0-full-rag-rewrite/phases/08.3-mcp-oauth-deploy-public-https/08.3-HUMAN-UAT.md`

(2 file YAML-spec plan internal `10-05-PLAN.md` + `08.3-04-PLAN.md` SKIP — tham chiếu `mcp.medinet.vn` ở các file này là decision-historical artifact thời điểm ship; PLAN.md/SUMMARY.md cùng cụm đã có note dẫn đến quick task này.)

## Verification

- `caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile` → **Valid configuration** (chỉ warning carry forward về `header_up X-Forwarded-*` redundant từ Phase 5, không liên quan thay đổi này).
- `docker compose config --quiet` → PASS (với dummy env vars).
- Smoke runtime defer ops deploy: 
  - `curl https://wiki.medinet.vn/.well-known/oauth-authorization-server/mcp` → 200 + JSON OAuth metadata
  - `curl https://wiki.medinet.vn/mcp` → MCP Streamable HTTP root
  - `curl https://wiki.medinet.vn/.well-known/jwks.json` → 200 (JWKS Phase 3 vẫn route đúng tới central, Caddy auto-sort match `/.well-known/*` catch-all sau khi prefix dài `oauth-*` thắng)

## Backward incompat — operator broadcast

**Claude web connector** đang cấu hình issuer `https://mcp.medinet.vn` sẽ **bắt buộc re-register** với URL mới `https://wiki.medinet.vn/mcp` sau deploy. Tokens cấp bởi issuer cũ sẽ INVALID (issuer mismatch — OAuth spec). Communicate trước:
1. Update Claude web connector config: issuer URL `https://wiki.medinet.vn/mcp`.
2. Re-authorize user (user-driven OAuth flow lại).
3. Có thể giữ DNS record `mcp.medinet.vn` 7-14 ngày grace period với HTTP 301 redirect → `wiki.medinet.vn/mcp/...` để client cũ tự migrate (defer ops decision — không bao gồm trong quick task này).

## Rollback

Quick task = 1 atomic commit. Rollback qua:
```bash
git revert <commit-sha>
docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile
# Restore DNS A record mcp.medinet.vn → IP VPS (nếu đã gỡ)
# Operator restore MCP_PUBLIC_DOMAIN env trong .env
```

## Pitfall observed

Caddy `handle /.well-known/*` ambiguity: block wiki carry forward từ Phase 5 đã có catch-all route `/.well-known/*` → central API serve JWKS (Plan 03-01). Khi thêm OAuth well-known routes, **PHẢI** dùng prefix dài cụ thể (`/.well-known/oauth-authorization-server*` 40 char) để Caddy auto-sort match TRƯỚC catch-all (`/.well-known/*` 14 char). Test PASS qua `caddy validate`.

## Deferrals

- **Operator-facing**: VPS_DEPLOY.md update DONE — operator chỉ cần làm: (1) bỏ DNS A `mcp.medinet.vn`, (2) update `.env` 2 dòng (bỏ `MCP_PUBLIC_DOMAIN`, đổi `MCP_OAUTH_ISSUER_URL`), (3) `docker compose up -d --force-recreate caddy mcp_service`, (4) re-register Claude web connector với issuer mới.
- **Smoke runtime defer**: Phase 7 MIGRATE-05 pattern carry forward — runtime UAT defer ops deploy. Tài liệu acceptance criteria đã viết, ops verify khi deploy thật.
- **DNS grace redirect 301**: Không bao gồm trong quick task. Operator quyết định có giữ DNS `mcp.medinet.vn` + Caddy redirect block 7-14 ngày hay không.

## Reference

- Quick PLAN: [`.planning/quick/2026-05-23-mcp-subdomain-consolidate/PLAN.md`](PLAN.md)
- MCP service backend support: [`mcp_service/mcp_app/config.py:71`](../../../mcp_service/mcp_app/config.py) (`path_prefix` field) + [`mcp_service/mcp_app/server.py:562-568`](../../../mcp_service/mcp_app/server.py) (streamable_http_path conditional)
- Phase 5 Caddy pattern: [`.planning/phases/05-reverse-proxy-frontend-subpath/05-RESEARCH.md`](../../phases/05-reverse-proxy-frontend-subpath/05-RESEARCH.md) (Pattern 1 + Pitfall 10 specificity sort)
