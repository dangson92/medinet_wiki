"""Login form route cho OAuth flow — Phase 8.3 (MCP-01, D-02).

Bước login/consent của OAuth flow xác thực bằng tài khoản Medinet Wiki có sẵn
(D-02) — KHÔNG tạo identity mới. Route HTML form sống trong `mcp_app`, mount cạnh
các route metadata/`/authorize`/`/token` do SDK `mcp` 1.27 tự tạo.

Luồng:
- GET /login?txn=<txn>     -> trả HTML form (email + password).
- POST /login/callback     -> gọi `api_client.login()` xác thực credential Medinet;
  đúng -> `provider.complete_authorization()` phát code -> redirect 302 về client;
  sai -> render lại form kèm thông báo lỗi.

Bảo mật (T-08.3-08): KHÔNG bao giờ log email / password / JWT / txn. Lỗi hạ tầng
render thông báo chung "Lỗi hệ thống" — KHÔNG lộ stack trace cho user.
"""
from __future__ import annotations

import html
import logging

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response
from starlette.routing import Route

from mcp_app.api_client import ApiClient, ApiClientError
from mcp_app.oauth.provider import MedinetOAuthProvider
from mcp_app.oauth.store import OAuthStoreError

logger = logging.getLogger(__name__)


def render_login_form(txn: str, error: str | None = None) -> HTMLResponse:
    """Trả HTML form đăng nhập tối giản.

    Args:
        txn: transaction id — đặt vào hidden input để POST callback nối lại flow.
        error: thông báo lỗi (nếu có) — hiển thị dòng đỏ phía trên form.
    """
    safe_txn = html.escape(txn, quote=True)
    error_block = ""
    if error:
        error_block = (
            f'<p style="color:#c0392b;font-weight:bold">{html.escape(error)}</p>'
        )
    body = f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Đăng nhập Medinet Wiki</title>
</head>
<body style="font-family:sans-serif;max-width:360px;margin:48px auto">
  <h2>Đăng nhập Medinet Wiki</h2>
  <p>Đăng nhập bằng tài khoản Medinet Wiki để cấp quyền truy cập.</p>
  {error_block}
  <form method="post" action="/login/callback">
    <input type="hidden" name="txn" value="{safe_txn}">
    <p>
      <label for="email">Email</label><br>
      <input type="email" id="email" name="email" required
             style="width:100%;padding:6px">
    </p>
    <p>
      <label for="password">Mật khẩu</label><br>
      <input type="password" id="password" name="password" required
             style="width:100%;padding:6px">
    </p>
    <button type="submit" style="padding:8px 16px">Đăng nhập</button>
  </form>
</body>
</html>"""
    return HTMLResponse(body)


def get_login_routes(
    provider: MedinetOAuthProvider, api_client: ApiClient
) -> list[Route]:
    """Trả danh sách Route Starlette cho login form.

    Dùng closure để inject `provider` + `api_client` vào handler — tránh global.
    """

    async def login_get(request: Request) -> Response:
        """GET /login — trả HTML form. Thiếu `txn` -> 400."""
        txn = request.query_params.get("txn")
        if not txn:
            return HTMLResponse(
                "<p>Thiếu tham số txn — phiên đăng nhập không hợp lệ.</p>",
                status_code=400,
            )
        return render_login_form(txn)

    async def login_callback(request: Request) -> Response:
        """POST /login/callback — xác thực credential Medinet, phát code OAuth."""
        form = await request.form()
        txn = str(form.get("txn") or "")
        email = str(form.get("email") or "")
        password = str(form.get("password") or "")

        if not txn:
            return HTMLResponse(
                "<p>Thiếu tham số txn — phiên đăng nhập không hợp lệ.</p>",
                status_code=400,
            )

        # (a) Xác thực credential Medinet qua API Service — KHÔNG verify tại MCP.
        try:
            login_data = await api_client.login(email, password)
        except ApiClientError:
            logger.error("Login callback — lỗi hạ tầng khi gọi API Service")
            return render_login_form(
                txn, error="Lỗi hệ thống, vui lòng thử lại sau"
            )

        # (b) Credential sai -> render lại form kèm lỗi.
        if login_data is None:
            return render_login_form(txn, error="Sai tài khoản hoặc mật khẩu")

        # (c) Login OK -> phát authorization code, redirect về client.
        try:
            code, redirect_uri, client_state = await provider.complete_authorization(
                txn, login_data
            )
        except OAuthStoreError:
            logger.info("Login callback — txn hết hạn hoặc không hợp lệ")
            return render_login_form(
                txn, error="Phiên đăng nhập hết hạn, vui lòng kết nối lại"
            )

        location = f"{redirect_uri}?code={code}"
        if client_state is not None:
            location += f"&state={client_state}"
        logger.info("Login callback thành công — redirect về client")
        return RedirectResponse(location, status_code=302)

    return [
        Route("/login", login_get, methods=["GET"]),
        Route("/login/callback", login_callback, methods=["POST"]),
    ]
