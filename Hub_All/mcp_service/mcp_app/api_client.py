"""ApiClient — lớp gọi API Service qua HTTP (httpx).

Vì MCP Service nay là process độc lập (đảo D-04 Phase 8.1), nó gọi API Service qua HTTP
thay vì import service layer in-process. `ApiClient`:
- Dùng `httpx.AsyncClient` với timeout (chống request treo — T-08.2-01-D).
- Forward header `X-API-Key` client cung cấp xuống API Service.
- Unwrap envelope `{success, data, error, meta}` — trả thẳng `data` khi thành công.
- Map status/error code sang cây exception riêng cho tầng tool xử lý.

Bảo mật (T-08.2-01-I): KHÔNG bao giờ log `api_key`, header, hay URL kèm query string.
Khi log lỗi chỉ log `method`, `path`, `status_code`, `error.code`.

Phase 8.3 (MCP-01, D-02): thêm method `login()` gọi `POST /api/auth/login` để bước
login của OAuth flow xác thực bằng tài khoản Medinet — credential ủy thác hoàn toàn
API Service (Argon2), MCP Service KHÔNG tự verify password và KHÔNG log email/password.

Phase 8.3 Plan 03 (MCP-02, D-03): `_request`/`get`/`post` nay nhận thêm param `jwt`
— khi có JWT, forward header `Authorization: Bearer <JWT>` (danh tính theo từng user
OAuth) thay cho `X-API-Key`; nhánh `X-API-Key` GIỮ NGUYÊN cho client local. Thêm
method `refresh_jwt()` gọi `POST /api/auth/refresh` đổi JWT downstream mới khi JWT cũ
hết hạn giữa phiên OAuth dài (Pitfall 4) — refresh CÓ rotation (AUTH-02), caller
PHẢI lưu đè cả access + refresh token mới (Pitfall 5).
"""
from __future__ import annotations

import logging
from types import TracebackType
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class ApiClientError(Exception):
    """Lỗi gốc khi gọi API Service."""


class ApiUnauthorizedError(ApiClientError):
    """401 — API key thiếu, sai, hoặc đã thu hồi."""


class ApiForbiddenError(ApiClientError):
    """403 — bị từ chối do hub isolation (không có quyền hub)."""


class ApiBadRequestError(ApiClientError):
    """400 — request không hợp lệ (ví dụ query rỗng)."""


class ApiServerError(ApiClientError):
    """5xx hoặc lỗi nội bộ API Service (LLM_FAILED, EMBEDDING_FAILED, network)."""


class ApiClient:
    """Client HTTP gọi API Service, unwrap envelope, forward X-API-Key."""

    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self.base_url = base_url
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)

    async def aclose(self) -> None:
        """Đóng httpx client — giải phóng connection pool."""
        await self._client.aclose()

    async def __aenter__(self) -> ApiClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        api_key: str | None = None,
        jwt: str | None = None,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Gọi API Service và unwrap envelope. Map lỗi sang exception riêng.

        Credential: ưu tiên `jwt` (header `Authorization: Bearer <JWT>` — D-03);
        nếu không có jwt thì dùng `api_key` (header `X-API-Key` — nhánh client
        local). Thiếu cả hai → raise ApiClientError.

        KHÔNG log api_key, jwt, header, hay URL có query string (T-08.2-01-I).
        """
        if jwt:
            headers = {"Authorization": f"Bearer {jwt}"}
        elif api_key:
            headers = {"X-API-Key": api_key}
        else:
            raise ApiClientError("Thiếu credential — cần jwt hoặc api_key")
        try:
            resp = await self._client.request(
                method, path, headers=headers, json=json_body, params=params
            )
        except httpx.RequestError as e:
            logger.error("API Service không phản hồi: method=%s path=%s", method, path)
            raise ApiServerError(
                f"Không kết nối được API Service: {type(e).__name__}"
            ) from e

        try:
            envelope = resp.json()
        except ValueError as e:
            logger.error(
                "API Service trả response không hợp lệ: method=%s path=%s status_code=%s",
                method,
                path,
                resp.status_code,
            )
            raise ApiServerError(
                f"API Service trả response không hợp lệ (status {resp.status_code})"
            ) from e

        if resp.status_code == 200 and envelope.get("success") is True:
            return envelope.get("data")

        err = envelope.get("error") or {}
        code = err.get("code", "ERROR")
        message = err.get("message", "Lỗi không xác định")
        logger.error(
            "API Service trả lỗi: method=%s path=%s status_code=%s error_code=%s",
            method,
            path,
            resp.status_code,
            code,
        )

        if resp.status_code == 401:
            raise ApiUnauthorizedError(message)
        if resp.status_code == 403:
            raise ApiForbiddenError(message)
        if resp.status_code == 400:
            raise ApiBadRequestError(message)
        raise ApiServerError(f"{code}: {message}")

    async def get(
        self,
        path: str,
        *,
        api_key: str | None = None,
        jwt: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Gọi GET tới API Service — credential qua `jwt` hoặc `api_key`."""
        return await self._request(
            "GET", path, api_key=api_key, jwt=jwt, params=params
        )

    async def post(
        self,
        path: str,
        *,
        api_key: str | None = None,
        jwt: str | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        """Gọi POST tới API Service — credential qua `jwt` hoặc `api_key`."""
        return await self._request(
            "POST", path, api_key=api_key, jwt=jwt, json_body=json_body
        )

    async def login(self, email: str, password: str) -> dict | None:
        """Xác thực credential Medinet qua API Service (D-02). None nếu credential sai.

        Gọi POST /api/auth/login. KHÔNG verify password tại MCP Service — ủy thác
        hoàn toàn API Service (Argon2). Bảo mật: KHÔNG log email/password.

        Returns:
            - dict `{access_token, refresh_token, expires_at, user}` khi login OK.
            - `None` khi credential sai (HTTP 401) — kết quả hợp lệ của login form.

        Raises:
            ApiServerError: lỗi hạ tầng (network, 5xx, response không hợp lệ) — KHÁC
                credential sai; login form sẽ render lỗi hệ thống chung.
        """
        try:
            resp = await self._client.post(
                "/api/auth/login", json={"email": email, "password": password}
            )
        except httpx.RequestError as e:
            logger.error("API Service không phản hồi khi login: %s", type(e).__name__)
            raise ApiServerError(
                f"Không kết nối được API Service: {type(e).__name__}"
            ) from e

        try:
            envelope = resp.json()
        except ValueError as e:
            logger.error(
                "API Service trả response login không hợp lệ: status_code=%s",
                resp.status_code,
            )
            raise ApiServerError(
                f"API Service trả response không hợp lệ (status {resp.status_code})"
            ) from e

        if resp.status_code == 200 and envelope.get("success") is True:
            return envelope.get("data")  # {access_token, refresh_token, expires_at, user}
        if resp.status_code == 401:
            logger.info("Login thất bại — credential sai (status 401)")
            return None

        err = envelope.get("error") or {}
        code = err.get("code", "ERROR")
        message = err.get("message", "lỗi không xác định")
        logger.error(
            "API Service trả lỗi khi login: status_code=%s error_code=%s",
            resp.status_code,
            code,
        )
        raise ApiServerError(f"{code}: {message}")

    async def get_mcp_client_internal(
        self, client_id: str, *, internal_token: str
    ) -> dict | None:
        """Lookup pre-registered MCP OAuth client từ API service (Phase 8.3 per-user).

        Gọi `GET /api/internal/mcp/clients/{client_id}` với header
        `Authorization: Bearer <internal_token>` — shared secret giữa 2 service.

        Returns:
            - dict `{client_id, client_secret, redirect_uris, owner_user_id,
              owner_email}` khi client tồn tại trong API DB (per-user
              pre-registered, KHÔNG phải DCR).
            - `None` khi API trả 404 (client chưa registered) hoặc 503
              (endpoint chưa cấu hình MCP_INTERNAL_TOKEN — degrade an toàn
              về "không bind").

        Raises:
            ApiUnauthorizedError: 401 — internal_token sai (configuration bug).
            ApiServerError:       5xx / response không hợp lệ / network.

        Bảo mật: KHÔNG log `internal_token` hay `client_secret` (T-08.3-08).
        """
        path = f"/api/internal/mcp/clients/{client_id}"
        headers = {"Authorization": f"Bearer {internal_token}"}
        try:
            resp = await self._client.get(path, headers=headers)
        except httpx.RequestError as e:
            logger.error(
                "API Service không phản hồi khi lookup MCP client: %s",
                type(e).__name__,
            )
            raise ApiServerError(
                f"Không kết nối được API Service: {type(e).__name__}"
            ) from e

        try:
            envelope = resp.json()
        except ValueError as e:
            logger.error(
                "API Service trả response lookup MCP client không hợp lệ: status_code=%s",
                resp.status_code,
            )
            raise ApiServerError(
                f"API Service trả response không hợp lệ (status {resp.status_code})"
            ) from e

        if resp.status_code == 200 and envelope.get("success") is True:
            data = envelope.get("data")
            return data if isinstance(data, dict) else None
        if resp.status_code == 404:
            # Client chưa registered (DCR / không tồn tại) — KHÔNG log
            # client_id (PII nhẹ; chỉ log loại kết quả).
            logger.info("MCP client lookup — 404 not registered")
            return None
        if resp.status_code == 503:
            # API chưa cấu hình MCP_INTERNAL_TOKEN — log warning, degrade
            # về "không bind". Operator phải set env để bind enforce work.
            logger.warning(
                "API Service chưa cấu hình MCP_INTERNAL_TOKEN — bind enforce skipped"
            )
            return None

        err = envelope.get("error") or {}
        code = err.get("code", "ERROR")
        message = err.get("message", "lỗi không xác định")
        logger.error(
            "API Service trả lỗi khi lookup MCP client: status_code=%s error_code=%s",
            resp.status_code,
            code,
        )
        if resp.status_code == 401:
            raise ApiUnauthorizedError(message)
        raise ApiServerError(f"{code}: {message}")

    async def refresh_jwt(self, refresh_token: str) -> dict | None:
        """Đổi JWT downstream mới bằng refresh token API Service (Pitfall 4).

        Gọi POST /api/auth/refresh. JWT API Service access TTL chỉ 900s — phiên
        OAuth sống nhiều ngày → JWT hết hạn giữa phiên; method này refresh JWT.

        REFRESH CÓ ROTATION (AUTH-02) — refresh token cũ bị blacklist sau khi
        đổi; caller PHẢI lưu đè CẢ access + refresh token mới (Pitfall 5), nếu
        chỉ lưu access mới thì lần refresh kế tiếp dùng refresh đã blacklist.

        Bảo mật: KHÔNG log refresh token hay JWT.

        Returns:
            - dict `{access_token, refresh_token, expires_at, user}` khi refresh OK.
            - `None` khi refresh token hết hạn/blacklist (HTTP 401) — caller map
              sang ToolError MCP_UNAUTHORIZED yêu cầu re-connect.

        Raises:
            ApiServerError: lỗi hạ tầng (network, 5xx, response không hợp lệ).
        """
        try:
            resp = await self._client.post(
                "/api/auth/refresh", json={"refresh_token": refresh_token}
            )
        except httpx.RequestError as e:
            logger.error("API Service không phản hồi khi refresh: %s", type(e).__name__)
            raise ApiServerError(
                f"Không kết nối được API Service: {type(e).__name__}"
            ) from e

        try:
            envelope = resp.json()
        except ValueError as e:
            logger.error(
                "API Service trả response refresh không hợp lệ: status_code=%s",
                resp.status_code,
            )
            raise ApiServerError(
                f"API Service trả response không hợp lệ (status {resp.status_code})"
            ) from e

        if resp.status_code == 200 and envelope.get("success") is True:
            return envelope.get("data")  # {access_token, refresh_token, expires_at, user}
        if resp.status_code == 401:
            logger.info("Refresh JWT thất bại — refresh token hết hạn (status 401)")
            return None

        err = envelope.get("error") or {}
        code = err.get("code", "ERROR")
        message = err.get("message", "lỗi không xác định")
        logger.error(
            "API Service trả lỗi khi refresh: status_code=%s error_code=%s",
            resp.status_code,
            code,
        )
        raise ApiServerError(f"{code}: {message}")
