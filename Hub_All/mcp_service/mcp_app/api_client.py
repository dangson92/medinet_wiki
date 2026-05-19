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
        api_key: str,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Gọi API Service và unwrap envelope. Map lỗi sang exception riêng.

        KHÔNG log api_key, header, hay URL có query string (T-08.2-01-I).
        """
        headers = {"X-API-Key": api_key}
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
        api_key: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Gọi GET tới API Service."""
        return await self._request("GET", path, api_key=api_key, params=params)

    async def post(
        self,
        path: str,
        *,
        api_key: str,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        """Gọi POST tới API Service."""
        return await self._request("POST", path, api_key=api_key, json_body=json_body)

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
