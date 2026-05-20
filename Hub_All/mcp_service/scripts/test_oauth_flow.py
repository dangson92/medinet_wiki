"""End-to-end OAuth flow test cho MCP service — verify server (Inspector bypass).

Chạy:
    cd Hub_All/mcp_service
    uv run python scripts/test_oauth_flow.py

Sẽ prompt email + password Medinet. Sau đó:
  1. DCR — đăng ký client mới qua /mcp/register.
  2. PKCE — sinh code_verifier + code_challenge.
  3. /mcp/authorize → 302 tới /mcp/login?txn=...
  4. POST /mcp/login/callback với email/password → 302 với code.
  5. /mcp/token đổi code → access_token.
  6. /mcp/ initialize (JSON-RPC) với Bearer token.
  7. /mcp/ tools/list — kỳ vọng 3 tool.
  8. /mcp/ tools/call list_hubs — kỳ vọng JSON list hub.

Mỗi bước in status code + snippet body. Stop ở bước fail.
"""
from __future__ import annotations

import asyncio
import base64
import getpass
import hashlib
import secrets
from urllib.parse import parse_qs, urlparse

import httpx

MCP_URL = "https://wiki.dangthanhson.com/mcp"
REDIRECT_URI = "http://localhost:8765/cb"


def _pkce() -> tuple[str, str]:
    """Generate PKCE code_verifier + code_challenge (S256)."""
    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    return verifier, challenge


def _step(n: int, title: str, status: int, body: str = "", short: bool = False) -> None:
    """Pretty-print step result."""
    marker = "✓" if 200 <= status < 400 else "✗"
    print(f"\n[{n}] {marker} {title}: HTTP {status}")
    if body:
        snippet = body[:200] if short else body[:600]
        print(f"    body: {snippet}")


async def main() -> int:
    print("=" * 60)
    print("MCP OAuth E2E test — bypass Inspector")
    print(f"Server: {MCP_URL}")
    print("=" * 60)

    email = input("Email Medinet: ").strip()
    password = getpass.getpass("Password (ẩn): ")
    if not email or not password:
        print("Email/password rỗng — dừng.")
        return 1

    async with httpx.AsyncClient(follow_redirects=False, timeout=30.0) as cli:
        # 1. DCR
        r = await cli.post(
            f"{MCP_URL}/register",
            json={
                "client_name": "OAuth E2E test script",
                "redirect_uris": [REDIRECT_URI],
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "token_endpoint_auth_method": "client_secret_post",
                "scope": "wiki",
            },
            headers={"Content-Type": "application/json"},
        )
        _step(1, "DCR /mcp/register", r.status_code, r.text, short=True)
        if r.status_code not in (200, 201):
            return 1
        ci = r.json()
        client_id = ci["client_id"]
        client_secret = ci["client_secret"]
        print(f"    client_id={client_id}")

        # 2. PKCE
        verifier, challenge = _pkce()
        state = secrets.token_urlsafe(16)
        print(f"\n[2] ✓ PKCE: challenge={challenge[:16]}... state={state[:16]}...")

        # 3. /authorize → expect 302 to /login
        r = await cli.get(
            f"{MCP_URL}/authorize",
            params={
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": REDIRECT_URI,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "state": state,
                "scope": "wiki",
                "resource": MCP_URL,
            },
        )
        _step(3, "GET /mcp/authorize", r.status_code, r.text, short=True)
        if r.status_code != 302:
            return 1
        login_url = r.headers["location"]
        print(f"    redirect → {login_url}")
        try:
            txn = parse_qs(urlparse(login_url).query)["txn"][0]
        except (KeyError, IndexError):
            print("    ✗ Không thấy txn trong query string")
            return 1
        print(f"    txn={txn[:16]}...")

        # 4. POST /login/callback (skip GET /login form — submit thẳng)
        r = await cli.post(
            f"{MCP_URL}/login/callback",
            data={"txn": txn, "email": email, "password": password},
        )
        _step(4, "POST /mcp/login/callback", r.status_code, r.text, short=True)
        if r.status_code != 302:
            return 1
        cb_url = r.headers["location"]
        print(f"    redirect → {cb_url}")
        try:
            code = parse_qs(urlparse(cb_url).query)["code"][0]
        except (KeyError, IndexError):
            print("    ✗ Không thấy code trong callback URL")
            return 1
        print(f"    code={code[:16]}...")

        # 5. POST /token
        r = await cli.post(
            f"{MCP_URL}/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "client_id": client_id,
                "client_secret": client_secret,
                "code_verifier": verifier,
            },
        )
        _step(5, "POST /mcp/token", r.status_code, r.text, short=True)
        if r.status_code != 200:
            return 1
        token = r.json()
        access_token = token["access_token"]
        print(f"    access_token={access_token[:20]}...")
        print(f"    expires_in={token.get('expires_in')}")

        # 6. initialize (transport endpoint, with trailing slash to bypass 307)
        bearer_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        r = await cli.post(
            f"{MCP_URL}/",
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-script", "version": "1.0"},
                },
                "id": 1,
            },
            headers=bearer_headers,
        )
        _step(6, "POST /mcp/ initialize", r.status_code, r.text)
        if r.status_code != 200:
            return 1

        # 7. tools/list
        r = await cli.post(
            f"{MCP_URL}/",
            json={"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 2},
            headers=bearer_headers,
        )
        _step(7, "POST /mcp/ tools/list", r.status_code, r.text)
        if r.status_code != 200:
            return 1

        # 8. tools/call list_hubs
        r = await cli.post(
            f"{MCP_URL}/",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": "list_hubs", "arguments": {}},
                "id": 3,
            },
            headers=bearer_headers,
        )
        _step(8, "POST /mcp/ tools/call list_hubs", r.status_code, r.text)
        if r.status_code != 200:
            return 1

        print("\n" + "=" * 60)
        print("✓ FULL FLOW OK — server OAuth + tool call hoạt động.")
        print("=" * 60)
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
