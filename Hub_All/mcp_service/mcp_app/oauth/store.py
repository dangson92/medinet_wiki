"""OAuthStore — lớp persistence SQLite cho toàn bộ OAuth state của MCP Service.

Phase 8.3 (MCP-01) thêm lớp OAuth: MCP Service nay đóng vai Authorization Server,
cần lưu state bền (sống sót restart — RESEARCH.md Pitfall 3). KHÁC Phase 8.2 ở chỗ
MCP Service nay CÓ một store cục bộ — nhưng vẫn KHÔNG chạm DB/Redis chung của API
Service (Phase 8.2 boundary). Store dùng một file SQLite cục bộ qua `aiosqlite`
(async — không block event loop).

Store quản 4 bảng:
- `oauth_clients`     — registered clients DCR (RFC 7591).
- `oauth_auth_codes` — authorization codes kèm downstream JWT/refresh API Service.
- `oauth_tokens`     — OAuth access/refresh token kèm downstream JWT/refresh.
- `oauth_pending`    — tham số authorize() giữa lúc /authorize và lúc user login.

Bảo mật (T-08.3-01 / T-08.2-01-I): KHÔNG bao giờ log giá trị token / JWT / code /
password. Khi log chỉ log `client_id`, số bản ghi, hoặc loại exception.
Mọi query dùng placeholder `?` (parametrized) — KHÔNG string interpolation
(T-08.3-04 — chống SQL injection từ client_id/code/txn do client cung cấp).
"""
from __future__ import annotations

import json
import logging
import os
from types import TracebackType

import aiosqlite

logger = logging.getLogger(__name__)


class OAuthStoreError(Exception):
    """Lỗi gốc khi thao tác OAuth state store."""


_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS oauth_clients (
        client_id TEXT PRIMARY KEY,
        client_metadata TEXT NOT NULL,
        created_at INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS oauth_auth_codes (
        code TEXT PRIMARY KEY,
        client_id TEXT NOT NULL,
        code_payload TEXT NOT NULL,
        downstream_jwt TEXT NOT NULL,
        downstream_refresh_token TEXT NOT NULL,
        user_payload TEXT NOT NULL,
        expires_at INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS oauth_tokens (
        access_token TEXT PRIMARY KEY,
        refresh_token TEXT,
        client_id TEXT NOT NULL,
        scopes TEXT NOT NULL,
        downstream_jwt TEXT NOT NULL,
        downstream_refresh_token TEXT NOT NULL,
        user_payload TEXT NOT NULL,
        expires_at INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS oauth_pending (
        txn TEXT PRIMARY KEY,
        client_id TEXT NOT NULL,
        redirect_uri TEXT NOT NULL,
        code_challenge TEXT NOT NULL,
        code_challenge_method TEXT NOT NULL,
        client_state TEXT,
        scopes TEXT NOT NULL,
        created_at INTEGER NOT NULL
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_oauth_tokens_refresh
        ON oauth_tokens(refresh_token)
    """,
)


class OAuthStore:
    """SQLite persistence cho clients / auth_codes / tokens / pending.

    Dùng một connection mở sau `init_schema()` và giữ xuyên suốt vòng đời store
    (cần để fixture test dùng SQLite `:memory:` — đóng connection = mất DB).
    Gọi `aclose()` khi kết thúc để giải phóng connection.
    """

    def __init__(self, db_path: str) -> None:
        """Lưu `db_path`. KHÔNG mở connection ngay — lazy tới `init_schema()`."""
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def init_schema(self) -> None:
        """Mở connection + tạo 4 bảng (CREATE TABLE IF NOT EXISTS — idempotent)."""
        if self._conn is None:
            # Đảm bảo thư mục cha tồn tại (bỏ qua khi :memory: hoặc không có dirname).
            dirname = os.path.dirname(self.db_path)
            if dirname:
                os.makedirs(dirname, exist_ok=True)
            self._conn = await aiosqlite.connect(self.db_path)
        for statement in _SCHEMA_STATEMENTS:
            await self._conn.execute(statement)
        await self._conn.commit()
        logger.info("OAuthStore khởi tạo schema — 4 bảng sẵn sàng")

    def _require_conn(self) -> aiosqlite.Connection:
        """Trả connection đang mở, raise nếu chưa `init_schema()`."""
        if self._conn is None:
            raise OAuthStoreError("OAuthStore chưa init_schema() — chưa có connection")
        return self._conn

    async def aclose(self) -> None:
        """Đóng connection SQLite nếu đang mở."""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def __aenter__(self) -> OAuthStore:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    # --- oauth_clients (DCR) ---

    async def save_client(self, client_id: str, client_metadata: dict) -> None:
        """Lưu/ghi đè client DCR. `client_metadata` serialize JSON."""
        conn = self._require_conn()
        import time

        await conn.execute(
            "INSERT OR REPLACE INTO oauth_clients "
            "(client_id, client_metadata, created_at) VALUES (?, ?, ?)",
            (client_id, json.dumps(client_metadata), int(time.time())),
        )
        await conn.commit()
        logger.info("OAuthStore lưu client: client_id=%s", client_id)

    async def get_client(self, client_id: str) -> dict | None:
        """Đọc client metadata. None nếu không tồn tại."""
        conn = self._require_conn()
        async with conn.execute(
            "SELECT client_metadata FROM oauth_clients WHERE client_id = ?",
            (client_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    # --- oauth_auth_codes ---

    async def save_auth_code(
        self,
        code: str,
        client_id: str,
        code_payload: dict,
        downstream_jwt: str,
        downstream_refresh_token: str,
        user_payload: dict,
        expires_at: int,
    ) -> None:
        """Lưu authorization code kèm downstream JWT + user payload."""
        conn = self._require_conn()
        await conn.execute(
            "INSERT OR REPLACE INTO oauth_auth_codes "
            "(code, client_id, code_payload, downstream_jwt, "
            "downstream_refresh_token, user_payload, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                code,
                client_id,
                json.dumps(code_payload),
                downstream_jwt,
                downstream_refresh_token,
                json.dumps(user_payload),
                expires_at,
            ),
        )
        await conn.commit()
        logger.info("OAuthStore lưu auth code cho client_id=%s", client_id)

    async def load_auth_code(self, code: str) -> dict | None:
        """Đọc authorization code. None nếu không tồn tại (đã dùng/hết hạn)."""
        conn = self._require_conn()
        async with conn.execute(
            "SELECT client_id, code_payload, downstream_jwt, "
            "downstream_refresh_token, user_payload, expires_at "
            "FROM oauth_auth_codes WHERE code = ?",
            (code,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return {
            "client_id": row[0],
            "code_payload": json.loads(row[1]),
            "downstream_jwt": row[2],
            "downstream_refresh_token": row[3],
            "user_payload": json.loads(row[4]),
            "expires_at": row[5],
        }

    async def claim_auth_code(self, code: str) -> dict | None:
        """Đọc + xoá authorization code trong MỘT bước nguyên tử (DELETE ... RETURNING).

        Khác load_auth_code: claim_auth_code XOÁ code ngay khi đọc — nếu thao tác
        save_token kế tiếp lỗi, code KHÔNG còn trong store để replay (CR-01,
        RFC 6749 §10.5). Trả None nếu code không tồn tại (đã bị claim trước đó).
        Lưu ý: claim_auth_code KHÔNG kiểm expires_at — caller (provider) tự kiểm
        hạn sau khi claim.
        """
        conn = self._require_conn()
        async with conn.execute(
            "DELETE FROM oauth_auth_codes WHERE code = ? RETURNING "
            "client_id, code_payload, downstream_jwt, "
            "downstream_refresh_token, user_payload, expires_at",
            (code,),
        ) as cursor:
            row = await cursor.fetchone()
        await conn.commit()
        if row is None:
            return None
        return {
            "client_id": row[0],
            "code_payload": json.loads(row[1]),
            "downstream_jwt": row[2],
            "downstream_refresh_token": row[3],
            "user_payload": json.loads(row[4]),
            "expires_at": row[5],
        }

    async def delete_auth_code(self, code: str) -> None:
        """Xoá authorization code (single-use sau khi exchange)."""
        conn = self._require_conn()
        await conn.execute("DELETE FROM oauth_auth_codes WHERE code = ?", (code,))
        await conn.commit()

    # --- oauth_tokens ---

    async def save_token(
        self,
        access_token: str,
        refresh_token: str | None,
        client_id: str,
        scopes: list,
        downstream_jwt: str,
        downstream_refresh_token: str,
        user_payload: dict,
        expires_at: int,
    ) -> None:
        """Lưu OAuth token kèm downstream JWT + refresh + user payload."""
        conn = self._require_conn()
        await conn.execute(
            "INSERT OR REPLACE INTO oauth_tokens "
            "(access_token, refresh_token, client_id, scopes, downstream_jwt, "
            "downstream_refresh_token, user_payload, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                access_token,
                refresh_token,
                client_id,
                json.dumps(scopes),
                downstream_jwt,
                downstream_refresh_token,
                json.dumps(user_payload),
                expires_at,
            ),
        )
        await conn.commit()
        logger.info("OAuthStore lưu OAuth token cho client_id=%s", client_id)

    @staticmethod
    def _row_to_token(row: tuple) -> dict:
        """Map row oauth_tokens → dict."""
        return {
            "access_token": row[0],
            "refresh_token": row[1],
            "client_id": row[2],
            "scopes": json.loads(row[3]),
            "downstream_jwt": row[4],
            "downstream_refresh_token": row[5],
            "user_payload": json.loads(row[6]),
            "expires_at": row[7],
        }

    _TOKEN_COLUMNS = (
        "access_token, refresh_token, client_id, scopes, downstream_jwt, "
        "downstream_refresh_token, user_payload, expires_at"
    )

    async def load_token(self, access_token: str) -> dict | None:
        """Đọc OAuth token theo access_token. None nếu không tồn tại."""
        conn = self._require_conn()
        async with conn.execute(
            f"SELECT {self._TOKEN_COLUMNS} FROM oauth_tokens WHERE access_token = ?",
            (access_token,),
        ) as cursor:
            row = await cursor.fetchone()
        return self._row_to_token(row) if row is not None else None

    async def load_token_by_refresh(self, refresh_token: str) -> dict | None:
        """Đọc OAuth token theo refresh_token. None nếu không tồn tại."""
        conn = self._require_conn()
        async with conn.execute(
            f"SELECT {self._TOKEN_COLUMNS} FROM oauth_tokens WHERE refresh_token = ?",
            (refresh_token,),
        ) as cursor:
            row = await cursor.fetchone()
        return self._row_to_token(row) if row is not None else None

    async def update_downstream_jwt(
        self, access_token: str, new_jwt: str, new_refresh: str
    ) -> None:
        """Ghi đè CẢ downstream_jwt và downstream_refresh_token (Pitfall 5).

        API Service refresh CÓ rotation — nếu chỉ lưu JWT mới mà giữ refresh cũ
        thì lần refresh kế tiếp dùng refresh đã blacklist → fail.
        """
        conn = self._require_conn()
        await conn.execute(
            "UPDATE oauth_tokens SET downstream_jwt = ?, "
            "downstream_refresh_token = ? WHERE access_token = ?",
            (new_jwt, new_refresh, access_token),
        )
        await conn.commit()

    async def update_oauth_token(
        self,
        old_access_token: str,
        new_access_token: str,
        new_refresh_token: str,
        expires_at: int,
    ) -> None:
        """Rotate token OAuth khi exchange_refresh_token — đổi cả access + refresh."""
        conn = self._require_conn()
        await conn.execute(
            "UPDATE oauth_tokens SET access_token = ?, refresh_token = ?, "
            "expires_at = ? WHERE access_token = ?",
            (new_access_token, new_refresh_token, expires_at, old_access_token),
        )
        await conn.commit()

    async def rotate_token(
        self,
        old_refresh_token: str,
        new_access_token: str,
        new_refresh_token: str,
        expires_at: int,
    ) -> bool:
        """Rotate token OAuth định vị theo refresh_token (giá trị caller cầm).

        Trả True nếu UPDATE khớp đúng 1 dòng; False nếu refresh token đã bị dùng/
        rotate (rowcount != 1) — caller PHẢI coi đây là refresh-token reuse và từ
        chối (CR-02, RFC 6749 §10.4). Khác update_oauth_token: định vị theo
        refresh_token + kiểm rowcount thay vì WHERE access_token đã hết hạn.
        """
        conn = self._require_conn()
        cursor = await conn.execute(
            "UPDATE oauth_tokens SET access_token = ?, refresh_token = ?, "
            "expires_at = ? WHERE refresh_token = ?",
            (new_access_token, new_refresh_token, expires_at, old_refresh_token),
        )
        await conn.commit()
        return cursor.rowcount == 1

    async def delete_token(self, access_token: str) -> None:
        """Xoá OAuth token (hỗ trợ revoke)."""
        conn = self._require_conn()
        await conn.execute(
            "DELETE FROM oauth_tokens WHERE access_token = ?", (access_token,)
        )
        await conn.commit()

    # --- oauth_pending ---

    async def save_pending(
        self,
        txn: str,
        client_id: str,
        redirect_uri: str,
        code_challenge: str,
        code_challenge_method: str,
        client_state: str | None,
        scopes: list,
        created_at: int,
    ) -> None:
        """Lưu tham số authorize() — giữ giữa lúc /authorize và lúc user login."""
        conn = self._require_conn()
        await conn.execute(
            "INSERT OR REPLACE INTO oauth_pending "
            "(txn, client_id, redirect_uri, code_challenge, code_challenge_method, "
            "client_state, scopes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                txn,
                client_id,
                redirect_uri,
                code_challenge,
                code_challenge_method,
                client_state,
                json.dumps(scopes),
                created_at,
            ),
        )
        await conn.commit()
        logger.info("OAuthStore lưu pending authorize cho client_id=%s", client_id)

    async def load_pending(self, txn: str) -> dict | None:
        """Đọc pending authorize theo txn. None nếu không tồn tại (đã dùng/hết hạn)."""
        conn = self._require_conn()
        async with conn.execute(
            "SELECT client_id, redirect_uri, code_challenge, code_challenge_method, "
            "client_state, scopes, created_at FROM oauth_pending WHERE txn = ?",
            (txn,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return {
            "client_id": row[0],
            "redirect_uri": row[1],
            "code_challenge": row[2],
            "code_challenge_method": row[3],
            "client_state": row[4],
            "scopes": json.loads(row[5]),
            "created_at": row[6],
        }

    async def delete_pending(self, txn: str) -> None:
        """Xoá pending authorize (dùng 1 lần sau khi login callback nối lại flow)."""
        conn = self._require_conn()
        await conn.execute("DELETE FROM oauth_pending WHERE txn = ?", (txn,))
        await conn.commit()

    # --- cleanup ---

    async def cleanup_expired(self, now: int) -> None:
        """Dọn auth code hết hạn + pending bỏ dở quá 10 phút (>600s)."""
        conn = self._require_conn()
        await conn.execute(
            "DELETE FROM oauth_auth_codes WHERE expires_at < ?", (now,)
        )
        await conn.execute(
            "DELETE FROM oauth_pending WHERE created_at < ?", (now - 600,)
        )
        await conn.commit()
        logger.info("OAuthStore cleanup_expired hoàn tất")
