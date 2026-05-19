"""ApiClient — lớp gọi API Service qua HTTP (httpx).

Vì MCP Service nay là process độc lập (đảo D-04 Phase 8.1), nó gọi API Service qua HTTP
thay vì import service layer in-process. `ApiClient`:
- Dùng `httpx.AsyncClient` với timeout (chống request treo — T-08.2-01-D).
- Forward header `X-API-Key` client cung cấp xuống API Service.
- Unwrap envelope `{success, data, error, meta}` — trả thẳng `data` khi thành công.
- Map status/error code sang cây exception riêng cho tầng tool xử lý.

Bảo mật (T-08.2-01-I): KHÔNG bao giờ log `api_key`, header, hay URL kèm query string.
Khi log lỗi chỉ log `method`, `path`, `status_code`, `error.code`.
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
