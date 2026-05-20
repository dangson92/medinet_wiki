"""CLI sinh + đăng ký pre-registered OAuth client cho Claude web.

Khi user dùng "Add custom connector" của Claude web ở chế độ **Advanced**
(nhập tay Client ID + Client Secret thay vì để Claude tự DCR), MCP Service
cần CÓ SẴN một row tương ứng trong bảng `oauth_clients` — nếu không,
provider trả `get_client() = None` và toàn bộ flow OAuth hỏng ngay bước
authorize.

CLI này (chạy 1 lần trong container `mcp_service`):
1. Sinh `client_id` + `client_secret` ngẫu nhiên đủ entropy.
2. Lắp thành `OAuthClientInformationFull` khớp schema SDK (RFC 7591).
3. INSERT OR REPLACE vào bảng `oauth_clients` qua `OAuthStore`.
4. In 2 chuỗi ra stdout — admin copy dán vào dialog Claude + tab
   Settings → MCP Connector.

Sử dụng (trong container `mcp_service`):

    python -m mcp_app.oauth.create_client \\
        --redirect-uri https://claude.ai/api/mcp/auth_callback

Lấy redirect_uri từ dialog "Add custom connector" của Claude web — dialog
hiển thị URL callback khi user chọn Advanced. Lặp `--redirect-uri` nhiều
lần để hỗ trợ nhiều môi trường (vd staging + prod).

Bảo mật (kế thừa nguyên tắc T-08.3-08):
- `client_id` mang prefix `mcp_` để phân biệt với DCR (SDK sinh prefix khác);
  hậu tố 16 byte urlsafe (~128 bit entropy) → đủ chống đoán.
- `client_secret` 32 byte urlsafe (~256 bit entropy) — vượt khuyến nghị
  RFC 6749 §10.10.
- KHÔNG log giá trị secret; chỉ in 1 lần ra stdout cho admin copy.
- INSERT OR REPLACE đảm bảo chạy lại không cộng dồn rác — mỗi lần chạy
  tạo row MỚI (client_id khác), row cũ ở lại tới khi admin xoá tay.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import secrets
import sys
import time

from mcp.shared.auth import OAuthClientInformationFull
from pydantic import AnyUrl

from mcp_app.config import get_settings
from mcp_app.oauth.store import OAuthStore

# redirect_uri mặc định của Claude web khi thêm custom connector (xác nhận
# qua test fixture mcp_service/tests/test_oauth_provider.py:51). Nếu Claude
# đổi URL trong tương lai, dùng `--redirect-uri` override.
_DEFAULT_REDIRECT_URI = "https://claude.ai/api/mcp/auth_callback"


def _generate_client_id() -> str:
    """Sinh client_id dạng `mcp_<22 urlsafe chars>` — đủ entropy, dễ nhận diện."""
    return f"mcp_{secrets.token_urlsafe(16)}"


def _generate_client_secret() -> str:
    """Sinh client_secret 32-byte urlsafe (~256 bit entropy)."""
    return secrets.token_urlsafe(32)


async def _register(
    *,
    db_path: str,
    redirect_uris: list[str],
    client_name: str,
) -> tuple[str, str]:
    """Mở store, sinh credentials, lưu, đóng store. Trả `(client_id, secret)`.

    Tách khỏi `main()` để test gọi được trực tiếp với tmp path.
    """
    client_id = _generate_client_id()
    client_secret = _generate_client_secret()
    now = int(time.time())

    info = OAuthClientInformationFull(
        client_id=client_id,
        client_secret=client_secret,
        client_id_issued_at=now,
        # 0 = không hết hạn theo RFC 7591 §3.2.1. Admin xoay secret bằng
        # cách chạy lại CLI sinh row mới.
        client_secret_expires_at=0,
        redirect_uris=[AnyUrl(uri) for uri in redirect_uris],
        # client_secret_post: client gửi secret trong body POST /token —
        # tương thích rộng, không yêu cầu Basic auth header.
        token_endpoint_auth_method="client_secret_post",
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
        scope="wiki",
        client_name=client_name,
    )

    store = OAuthStore(db_path)
    await store.init_schema()
    try:
        await store.save_client(client_id, info.model_dump(mode="json"))
    finally:
        await store.aclose()

    return client_id, client_secret


def main(argv: list[str] | None = None) -> int:
    """Entrypoint CLI — parse argv, gọi `_register()`, in kết quả."""
    parser = argparse.ArgumentParser(
        prog="python -m mcp_app.oauth.create_client",
        description=(
            "Sinh + đăng ký pre-registered OAuth client cho Claude web "
            "(bỏ qua DCR — dùng khi điền thủ công Client ID/Secret ở "
            "Advanced của dialog Add custom connector)."
        ),
    )
    parser.add_argument(
        "--redirect-uri",
        action="append",
        dest="redirect_uris",
        metavar="URL",
        help=(
            "Callback URI Claude dùng — lấy từ dialog Add custom connector. "
            "Lặp flag để thêm nhiều URI. "
            f"Mặc định: {_DEFAULT_REDIRECT_URI}"
        ),
    )
    parser.add_argument(
        "--client-name",
        default="Claude Web Connector",
        help="Tên client (chỉ để nhận diện trong store).",
    )
    args = parser.parse_args(argv)

    redirect_uris: list[str] = args.redirect_uris or [_DEFAULT_REDIRECT_URI]

    logging.basicConfig(level=logging.WARNING)
    settings = get_settings()

    client_id, client_secret = asyncio.run(
        _register(
            db_path=settings.oauth_state_db_path,
            redirect_uris=redirect_uris,
            client_name=args.client_name,
        )
    )

    # In ra stdout — admin copy. KHÔNG log qua logger (tránh đẩy secret
    # vào file log / structured log nếu sau này wire vào).
    print("=== Pre-registered OAuth client đã đăng ký ===")
    print(f"client_id      = {client_id}")
    print(f"client_secret  = {client_secret}")
    print(f"redirect_uris  = {', '.join(redirect_uris)}")
    print("scope          = wiki")
    print(f"store          = {settings.oauth_state_db_path}")
    print()
    print("Bước tiếp theo:")
    print("  1) Dán client_id + client_secret vào dialog Add custom connector")
    print("     (Advanced) của Claude web.")
    print("  2) Lưu 2 chuỗi vào Settings → MCP Connector để tiện copy lại sau.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
