---
title: Gộp MCP subdomain về wiki.medinet.vn/mcp
slug: mcp-subdomain-consolidate
date: 2026-05-23
status: complete
---

# Quick task — Gộp `mcp.medinet.vn` về `wiki.medinet.vn/mcp`

## Bối cảnh

Operator quyết định 2026-05-23 chỉ duy trì **1 public subdomain** `wiki.medinet.vn` cho cả wiki + MCP service. Subdomain riêng `mcp.medinet.vn` (Phase 8.3 M2 v2.0) không còn cần — gỡ để giảm DNS record, ACME cert, và cấu hình operator.

## Phát hiện audit

- MCP service **đã** support path-prefix mode (`MCP_PATH_PREFIX=mcp` + `oauth_issuer_url`) — ship từ M2 Phase 8.3. Backend KHÔNG cần thay đổi.
- Caddyfile có 2 server block tách biệt `{$MCP_PUBLIC_DOMAIN}` + `{$WIKI_PUBLIC_DOMAIN}` — chưa gộp.
- Block `wiki.medinet.vn` chỉ route `/yte/api/*`, `/api/*`, `/.well-known/*` (JWKS), SPA — **chưa có `/mcp/*` hoặc OAuth well-known**.
- `MCP_OAUTH_ISSUER_URL` cấu hình `https://mcp.medinet.vn/mcp` (.env.example + VPS_DEPLOY.md).

## Scope (user chọn option 1 — full migration)

### Code/config (4 file):
1. `Hub_All/Caddyfile` — bỏ block `{$MCP_PUBLIC_DOMAIN}`, thêm route `/mcp` + `/mcp/*` + `/.well-known/oauth-authorization-server*` + `/.well-known/oauth-protected-resource*` + `/.well-known/openid-configuration*` vào block wiki. Tách matcher cụ thể TRƯỚC catch-all `/.well-known/*` (JWKS Phase 3) để Caddy auto-sort match đúng.
2. `Hub_All/docker-compose.yml` — bỏ env `MCP_PUBLIC_DOMAIN` khỏi caddy service, update comment.
3. `Hub_All/mcp_service/.env.example` — `MCP_OAUTH_ISSUER_URL=https://mcp.medinet.vn/mcp` → `https://wiki.medinet.vn/mcp`.
4. `Hub_All/VPS_DEPLOY.md` — sửa 7 vị trí (DNS 2 record → 1, .env compose, healthcheck URL, security checklist).

### Planning historical (7 file — append 1-line deprecated note):
5. `.planning/phases/05-reverse-proxy-frontend-subpath/05-CONTEXT.md`
6. `.planning/phases/05-reverse-proxy-frontend-subpath/05-RESEARCH.md`
7. `.planning/milestones/v2.0-full-rag-rewrite/phases/10-hardening-observability-docs/10-05-SUMMARY.md`
8. `.planning/milestones/v2.0-full-rag-rewrite/phases/10-hardening-observability-docs/10-05-PLAN.md`
9. `.planning/milestones/v2.0-full-rag-rewrite/phases/08.3-mcp-oauth-deploy-public-https/08.3-MCP-AUDIT-2026-05-21.md`
10. `.planning/milestones/v2.0-full-rag-rewrite/phases/08.3-mcp-oauth-deploy-public-https/08.3-HUMAN-UAT.md`
11. `.planning/milestones/v2.0-full-rag-rewrite/phases/08.3-mcp-oauth-deploy-public-https/08.3-04-PLAN.md`

## Pitfall

**Caddy `/.well-known/*` routing ambiguity:** Block wiki có `handle /.well-known/*` route tới `python-api-central:8080` (JWKS Phase 3 Plan 03-01). Khi thêm OAuth well-known routes, **PHẢI** đặt prefix dài cụ thể TRƯỚC catch-all để Caddy auto-sort match `/.well-known/oauth-*` → MCP, còn `/.well-known/jwks.json` + future → central. Caddy v2 auto-sort handle theo path specificity (Pitfall 10 từ Plan 05-01).

**Backward incompat operator:** Sau deploy, Claude web connector hiện đang cấu hình với issuer `https://mcp.medinet.vn` sẽ **bắt buộc re-register** qua URL mới `https://wiki.medinet.vn/mcp`. Communicate trước deploy.

## Rollback

Revert commit qua `git revert <sha>` + reload caddy. Subdomain config sẵn ở git history nếu cần khôi phục.

## Acceptance

- `docker compose config --quiet` PASS post-edit.
- `caddy validate --config /etc/caddy/Caddyfile` PASS (skip runtime — defer ops deploy).
- 11 file changes commit atomic.
- Smoke OAuth discovery URL mới: `curl https://wiki.medinet.vn/.well-known/oauth-authorization-server/mcp` (defer ops verify).
