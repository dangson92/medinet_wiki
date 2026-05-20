"""MedinetOAuthProvider — lớp OAuth Authorization Server của MCP Service.

Phase 8.3 (MCP-01): MCP Service nay đóng vai Authorization Server thật — tự phát
OAuth token, hỗ trợ Dynamic Client Registration (DCR), authorize code flow.
KHÁC Phase 8.2 (chỉ X-API-Key pass-through): MCP Service nay sở hữu vòng đời token
OAuth riêng, lưu state qua `OAuthStore`.

Lớp kế thừa `OAuthAuthorizationServerProvider` của SDK `mcp` 1.27 — implement đủ
9 method SDK gọi. SDK lo phần "đúng spec" (metadata RFC 8414/9728, PKCE S256, DCR
RFC 7591, code exchange) — provider này chỉ lo 3 mảng glue: persistence (qua
`OAuthStore`), bind danh tính Medinet vào token, và pending-authorize transaction.

Bổ trợ `complete_authorization()` — login callback (login.py) gọi sau khi xác thực
credential Medinet thành công để phát authorization code bind downstream JWT.

Bảo mật (T-08.3-08): KHÔNG bao giờ log giá trị token / authorization code /
downstream JWT / txn. Chỉ log `client_id`, loại thao tác, trạng thái
(`expired`/`not_found`). DCR mở (D-01 Claude's Discretion) — gate bảo mật thật là
bước login credential Medinet, KHÔNG phải client registration.
"""
from __future__ import annotations

import logging
import secrets
import time

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import AnyUrl

from mcp_app.api_client import ApiClient, ApiClientError
from mcp_app.oauth.store import OAuthStore, OAuthStoreError


class BindMismatchError(Exception):
    """User login OAuth ≠ owner pre-registered client (Phase 8.3 add-on per-user).

    Raised từ `complete_authorization` khi client là pre-registered (có owner
    trong API DB) nhưng user vừa login bằng tài khoản khác. login_callback
    catch riêng → render thông báo "không khớp" thay vì 500 chung.
    """

logger = logging.getLogger(__name__)

# TTL (giây) của authorization code — ngắn, single-use (RFC 6749 §10.5).
_AUTH_CODE_TTL = 600

# TTL (giây) của pending-authorize transaction — khớp mốc 600s trong
# OAuthStore.cleanup_expired. WR-02: complete_authorization phải kiểm hạn.
_PENDING_TTL = 600


class MedinetOAuthProvider(
    OAuthAuthorizationServerProvider[AuthorizationCode, RefreshToken, AccessToken]
):
    """OAuth Authorization Server provider cho MCP Service.

    Dependency injected tường minh — KHÔNG tự khởi tạo singleton bên trong:
    - `store`: OAuthStore (persistence SQLite — Plan 01).
    - `api_client`: ApiClient (chỉ login.py dùng; provider giữ reference cho wiring).
    - `issuer_url`: URL public của AS — dùng dựng URL redirect tới login form.
    - `access_token_ttl` / `refresh_token_ttl`: lifetime token OAuth (giây).
    """

    def __init__(
        self,
        store: OAuthStore,
        api_client: ApiClient | None,
        issuer_url: str,
        access_token_ttl: int,
        refresh_token_ttl: int,
        internal_token: str = "",
    ) -> None:
        self._store = store
        self._api_client = api_client
        self._issuer_url = issuer_url.rstrip("/")
        self._access_token_ttl = access_token_ttl
        self._refresh_token_ttl = refresh_token_ttl
        # Shared secret cho `/api/internal/mcp/clients/{id}` lookup (Phase 8.3
        # per-user pre-registered). Rỗng = tắt fallback API + bind enforce.
        self._internal_token = internal_token

    @property
    def issuer_url(self) -> str:
        """Issuer URL public (đã strip trailing slash) — login.py dùng cho form action."""
        return self._issuer_url

    # --- helper nội bộ ---

    @staticmethod
    def _now() -> int:
        """Unix timestamp hiện tại (giây)."""
        return int(time.time())

    @staticmethod
    def _new_opaque() -> str:
        """Sinh token/code opaque ngẫu nhiên — >160 bit entropy (RFC 6749 §10.10)."""
        return secrets.token_urlsafe(32)

    # --- DCR (RFC 7591) ---

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        """Đọc client. Local store (DCR) trước, fallback API (per-user pre-registered).

        Phase 8.3 add-on: client_id KHÔNG ở local store có thể là per-user
        pre-registered (sinh qua API service `/api/mcp/my-oauth-client`). Hỏi
        `/api/internal/mcp/clients/{id}` qua shared secret. None nếu cả 2
        nguồn đều miss.
        """
        # 1. Local store — DCR clients đăng ký trực tiếp với MCP.
        metadata = await self._store.get_client(client_id)
        if metadata is not None:
            return OAuthClientInformationFull.model_validate(metadata)

        # 2. Fallback API — per-user pre-registered (Phase 8.3 add-on).
        info = await self._fetch_internal_client(client_id)
        if info is None:
            return None

        return OAuthClientInformationFull(
            client_id=info["client_id"],
            client_secret=info["client_secret"],
            redirect_uris=[AnyUrl(u) for u in info.get("redirect_uris", [])],
            # client_secret_post — debug log (0eeed2b) chứng minh Claude gửi
            # secret qua form body, KHÔNG Basic header. SDK ClientAuthenticator
            # đọc form_data["client_secret"] khi method = post → compare value.
            token_endpoint_auth_method="client_secret_post",
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            scope="wiki",
        )

    async def _fetch_internal_client(self, client_id: str) -> dict | None:
        """Helper gọi API internal lookup. None nếu thiếu config / 404 / lỗi.

        Degrade an toàn: lỗi API → None (không phá luồng DCR cũ). Bind
        enforcement ở complete_authorization xử lý riêng trường hợp client
        có owner mà không lookup được.
        """
        if self._api_client is None or not self._internal_token:
            return None
        try:
            return await self._api_client.get_mcp_client_internal(
                client_id, internal_token=self._internal_token
            )
        except ApiClientError as e:
            logger.warning(
                "MCP client internal lookup failed: %s — fallback DCR-only",
                type(e).__name__,
            )
            return None

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        """Lưu client DCR. DCR mở (D-01) — KHÔNG từ chối client."""
        client_id = client_info.client_id
        if client_id is None:
            # SDK sinh client_id trước khi gọi register_client; phòng vệ thêm.
            raise OAuthStoreError("register_client thiếu client_id")
        await self._store.save_client(
            client_id, client_info.model_dump(mode="json")
        )
        logger.info("MedinetOAuthProvider đăng ký client: client_id=%s", client_id)

    # --- authorize ---

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        """Lưu pending-authorize transaction, trả URL redirect tới login form.

        SDK đã validate client + redirect_uri + PKCE. Provider sinh `txn` ngẫu nhiên,
        lưu tham số authorize vào `oauth_pending`, redirect user tới `/login?txn=...`.
        Login callback (login.py) dùng `txn` để `load_pending` nối lại flow.
        """
        txn = self._new_opaque()
        await self._store.save_pending(
            txn=txn,
            client_id=client.client_id or "",
            redirect_uri=str(params.redirect_uri),
            code_challenge=params.code_challenge,
            code_challenge_method="S256",
            client_state=params.state,
            scopes=list(params.scopes or []),
            created_at=self._now(),
        )
        logger.info(
            "MedinetOAuthProvider authorize — pending lưu, client_id=%s",
            client.client_id,
        )
        return f"{self._issuer_url}/login?txn={txn}"

    async def complete_authorization(
        self, txn: str, login_data: dict
    ) -> tuple[str, str, str | None]:
        """Hoàn tất authorize sau login thành công — phát authorization code.

        Login callback gọi method này sau khi `api_client.login()` xác thực thành
        công. Code phát ra bind downstream JWT (access + refresh) + user payload.

        Args:
            txn: transaction id từ `/login?txn=...`.
            login_data: dict `{access_token, refresh_token, expires_at, user}` từ
                `api_client.login()`.

        Returns:
            `(code, redirect_uri, client_state)` — login callback dựng RedirectResponse.

        Raises:
            OAuthStoreError: nếu `txn` không tồn tại / đã dùng / hết hạn.
        """
        pending = await self._store.load_pending(txn)
        if pending is None or pending["created_at"] < self._now() - _PENDING_TTL:
            raise OAuthStoreError("Phiên authorize hết hạn hoặc không hợp lệ")

        required = ("access_token", "refresh_token", "user")
        if not isinstance(login_data, dict) or not all(
            login_data.get(k) for k in required
        ):
            raise OAuthStoreError(
                "Phản hồi login từ API Service thiếu trường bắt buộc"
            )

        # Bind enforcement (Phase 8.3 add-on per-user): nếu client_id là
        # per-user pre-registered (có owner ở API), user login PHẢI khớp owner.
        # Client DCR (không có ở API → lookup None) → skip bind, behavior cũ.
        client_id = pending["client_id"]
        internal_info = await self._fetch_internal_client(client_id)
        if internal_info is not None:
            owner_user_id = str(internal_info.get("owner_user_id") or "")
            login_user = login_data.get("user") or {}
            login_user_id = str(login_user.get("id") or "")
            if owner_user_id and login_user_id and owner_user_id != login_user_id:
                logger.warning(
                    "MedinetOAuthProvider bind mismatch — client_id=%s "
                    "owner_user=%s login_user=%s",
                    client_id,
                    owner_user_id,
                    login_user_id,
                )
                raise BindMismatchError(
                    "Tài khoản đăng nhập không khớp với chủ sở hữu connector"
                )

        code = self._new_opaque()
        code_payload = {
            "scopes": pending["scopes"],
            "redirect_uri": pending["redirect_uri"],
            "code_challenge": pending["code_challenge"],
            "code_challenge_method": pending["code_challenge_method"],
        }
        await self._store.save_auth_code(
            code=code,
            client_id=pending["client_id"],
            code_payload=code_payload,
            downstream_jwt=login_data["access_token"],
            downstream_refresh_token=login_data["refresh_token"],
            user_payload=login_data["user"],
            expires_at=self._now() + _AUTH_CODE_TTL,
        )
        await self._store.delete_pending(txn)
        logger.info(
            "MedinetOAuthProvider phát authorization code cho client_id=%s",
            pending["client_id"],
        )
        return code, pending["redirect_uri"], pending["client_state"]

    # --- authorization code ---

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        """Đọc authorization code. None nếu không tồn tại / hết hạn."""
        record = await self._store.load_auth_code(authorization_code)
        if record is None:
            return None
        if record["expires_at"] < self._now():
            logger.info("MedinetOAuthProvider authorization code expired")
            return None
        payload = record["code_payload"]
        return AuthorizationCode(
            code=authorization_code,
            scopes=payload["scopes"],
            expires_at=float(record["expires_at"]),
            client_id=record["client_id"],
            code_challenge=payload["code_challenge"],
            redirect_uri=AnyUrl(payload["redirect_uri"]),
            redirect_uri_provided_explicitly=True,
        )

    async def exchange_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: AuthorizationCode,
    ) -> OAuthToken:
        """Đổi authorization code lấy OAuth access + refresh token.

        Code single-use — xoá khỏi store sau exchange (RFC 6749 §10.5). Token mới
        bind downstream JWT/refresh + user payload từ record của code.
        """
        record = await self._store.claim_auth_code(authorization_code.code)
        if record is None:
            raise OAuthStoreError(
                "Authorization code không tồn tại hoặc đã dùng"
            )
        # Code đã bị xoá nguyên tử — nếu save_token lỗi, code KHÔNG còn để replay.
        # Kiểm hạn TẠI exchange: load_authorization_code đã kiểm expires_at,
        # nhưng exchange_authorization_code có thể bị gọi trực tiếp (bỏ qua
        # load_authorization_code) — claim_auth_code KHÔNG kiểm hạn. Vì vậy
        # phải tự reject code hết hạn ở đây (RFC 6749 §10.5).
        if record["expires_at"] < self._now():
            raise OAuthStoreError("Authorization code đã hết hạn")

        access_token = self._new_opaque()
        refresh_token = self._new_opaque()
        scopes = list(authorization_code.scopes)
        await self._store.save_token(
            access_token=access_token,
            refresh_token=refresh_token,
            client_id=record["client_id"],
            scopes=scopes,
            downstream_jwt=record["downstream_jwt"],
            downstream_refresh_token=record["downstream_refresh_token"],
            user_payload=record["user_payload"],
            expires_at=self._now() + self._access_token_ttl,
        )
        logger.info(
            "MedinetOAuthProvider exchange code -> token, client_id=%s",
            record["client_id"],
        )
        return OAuthToken(
            access_token=access_token,
            token_type="Bearer",
            expires_in=self._access_token_ttl,
            scope=" ".join(scopes) if scopes else None,
            refresh_token=refresh_token,
        )

    # --- refresh token ---

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        """Đọc refresh token. None nếu không tồn tại."""
        record = await self._store.load_token_by_refresh(refresh_token)
        if record is None:
            return None
        return RefreshToken(
            token=refresh_token,
            client_id=record["client_id"],
            scopes=record["scopes"],
            expires_at=None,
        )

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        """Rotate token OAuth — phát access + refresh mới, vô hiệu cặp cũ.

        Downstream JWT giữ nguyên — refresh downstream JWT là Plan 03.
        """
        record = await self._store.load_token_by_refresh(refresh_token.token)
        if record is None:
            raise OAuthStoreError("Refresh token không tồn tại hoặc đã dùng")

        new_access = self._new_opaque()
        new_refresh = self._new_opaque()
        ok = await self._store.rotate_token(
            old_refresh_token=refresh_token.token,
            new_access_token=new_access,
            new_refresh_token=new_refresh,
            expires_at=self._now() + self._access_token_ttl,
        )
        if not ok:
            # rowcount != 1 — refresh token đã bị dùng/rotate (reuse detected).
            logger.info(
                "MedinetOAuthProvider refresh token reuse — client_id=%s",
                record["client_id"],
            )
            raise OAuthStoreError(
                "Refresh token đã dùng — vui lòng kết nối lại"
            )
        result_scopes = scopes or record["scopes"]
        logger.info(
            "MedinetOAuthProvider rotate refresh token, client_id=%s",
            record["client_id"],
        )
        return OAuthToken(
            access_token=new_access,
            token_type="Bearer",
            expires_in=self._access_token_ttl,
            scope=" ".join(result_scopes) if result_scopes else None,
            refresh_token=new_refresh,
        )

    # --- access token (verify mỗi tool call) ---

    async def load_access_token(self, token: str) -> AccessToken | None:
        """Verify OAuth access token. None nếu không tồn tại hoặc hết hạn.

        SDK gọi method này mỗi tool call qua ProviderTokenVerifier.
        """
        record = await self._store.load_token(token)
        if record is None:
            return None
        if record["expires_at"] < self._now():
            logger.info("MedinetOAuthProvider access token expired")
            return None
        return AccessToken(
            token=token,
            client_id=record["client_id"],
            scopes=record["scopes"],
            expires_at=record["expires_at"],
        )

    # --- revoke ---

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        """Thu hồi token. Nhận access token hoặc refresh token.

        SDK truyền AccessToken hoặc RefreshToken — xoá record tương ứng. Xoá theo
        record nên thu hồi đồng thời cả access lẫn refresh của cùng token.
        """
        if isinstance(token, RefreshToken):
            record = await self._store.load_token_by_refresh(token.token)
        else:
            record = await self._store.load_token(token.token)
        if record is not None:
            await self._store.delete_token(record["access_token"])
        logger.info(
            "MedinetOAuthProvider revoke token, client_id=%s", token.client_id
        )
