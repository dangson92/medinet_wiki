"""Application settings — pydantic-settings BaseSettings.

Đọc env vars từ .env file (dev) hoặc OS env (prod). Type-safe, validate sớm.

Tham chiếu:
- .env.example (Plan 02) — danh sách env vars chuẩn.
- R5 Pitfall 2 — `app_namespace` cố định "medinet_prod" mọi env.
- R1 Pitfall 1 — `rag_embedding_dim=1536` pin để pgvector HNSW index work.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Plan 02-05 FACTOR-04 — Reserved hub names blacklist.
# Postgres có 4 template DB hệ thống (postgres/template0/template1) + schema mặc
# định "public" + role "medinet" (M2 carry forward — postgres_user/owner cho mọi
# DB nghiệp vụ) + DB internal cocoindex (R5 + P7 carry forward — separate khỏi
# user DB). Reserve 6 name này tránh hub_name=postgres làm CREATE DATABASE
# medinet_hub_postgres OK nhưng confuse + reserved "medinet" tránh hub_name=medinet
# làm DB name medinet_hub_medinet redundant + privilege escalation theory nếu
# someone alias trùng role. "central" KHÔNG trong blacklist — central là aggregator
# special-case mapping sang medinet_central (KHÔNG prefix medinet_hub_).
RESERVED_HUB_NAMES = frozenset({
    "postgres",    # Postgres default superuser DB
    "cocoindex",   # Internal cocoindex state DB (M2 ship)
    "template0",   # Postgres template (read-only system)
    "template1",   # Postgres template (writable system default)
    "public",      # Default schema name — collision với cocoindex_db_schema
    "medinet",     # Postgres role name (M2 init-db.sh OWNER) — privilege confuse
})


class Settings(BaseSettings):
    """Tổng hợp config runtime của Medinet Wiki API."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Runtime
    app_env: Literal["dev", "staging", "production"] = "dev"
    # 8180 — frontend api.ts hardcode (Hyper-V excluded range 8038-8137 Windows).
    app_port: int = 8180
    log_level: str = "info"
    log_format: Literal["json", "console"] = "json"

    # Hub identity — v3.0 TOPO-04 (Phase 1 multi-DB topology) + FACTOR-04 Plan 02-05.
    # central = aggregator (medinet_central DB), yte/duoc/hcns = sub-hub
    # (medinet_hub_<name> DB cùng instance). Process biết mình deploy
    # hub nào để chọn DSN + cocoindex flow name (Plan 04) + Alembic
    # target (Plan 03). Default "central" giữ M2 backward-compat.
    #
    # Plan 02-05 FACTOR-04 — Dynamic hub registration.
    # Đổi từ Literal[4 hub] sang str + regex validator để operator thêm hub mới
    # (vd phap_che, marketing) qua `make hub-add HUB=<name>` mà KHÔNG sửa code.
    # Validator (`_validate_hub_name` bên dưới) enforce Postgres identifier safe
    # (lowercase a-z first, a-z0-9_ rest, max 16 char total — Postgres identifier
    # 63 char limit minus "medinet_hub_" prefix 12 char = 51 char headroom, nhưng
    # 16 char cho dễ nhớ + URL prefix Phase 5 Caddy gọn). KHÔNG cho phép hyphen
    # (Postgres identifier quote requirement) hoặc uppercase (case-sensitivity confuse).
    hub_name: str = "central"

    # Postgres — KHÔNG default (bắt buộc qua env)
    database_url: str = Field(...)
    cocoindex_database_url: str = Field(...)

    # Redis — KHÔNG default (bắt buộc qua env)
    redis_url: str = Field(...)

    # CocoIndex (R5 mitigation — cố định namespace để không "biến mất" bảng giữa env)
    app_namespace: str = "medinet_prod"
    cocoindex_db_schema: str = "cocoindex"

    # Cocoindex 1.0.3 LMDB path (Q5 — replace COCOINDEX_DATABASE_URL Postgres
    # cocoindex 0.x assumption sai). Cocoindex internal state (memo cache,
    # fingerprint, lineage) lưu LMDB local filesystem. Default tương đối project root.
    # Default TƯƠNG ĐỐI `.cocoindex/` (không tiền tố `Hub_All/`) — writable trong
    # mọi cwd: chạy native uvicorn (cwd `api/`) hoặc container override env tuyệt đối.
    # Gap SC5 fix — Hub_All/ prefix gây Permission denied trong container.
    cocoindex_lmdb_path: Path = Path(".cocoindex/state.lmdb")

    # Watchdog timeout — Plan 04-05 REVISION 2 NEW (INGEST-06, P8 mitigation).
    # 5 phút headroom cho `cocoindex_app.update_blocking()` documents lớn (DOCX 50
    # trang + N×embed LiteLLM có thể chạy >2 phút). Tránh false-flip processing
    # rows. Configurable qua env `WATCHDOG_TIMEOUT_SECONDS`.
    watchdog_timeout_seconds: int = 300

    # JWT
    jwt_private_key_path: Path = Path("./keys/private.pem")
    jwt_public_key_path: Path = Path("./keys/public.pem")
    jwt_access_token_ttl: int = 900
    jwt_refresh_token_ttl: int = 604800
    # Phase 3 Plan 03-01 SSO-01 (D-V3-Phase3-A) — Hub con consume JWKS endpoint
    # từ central qua intra-network HTTP. Default None ở central (KHÔNG cần fetch
    # — central có local private.pem). Plan 03-02 add @model_validator
    # `_enforce_central_jwks_url_for_hub` enforce hub con phải set field này
    # KHÔNG None (fail-loud boot nếu thiếu).
    # docker-compose 3 hub con set env
    #   CENTRAL_JWKS_URL=http://python-api-central:8080/.well-known/jwks.json
    central_jwks_url: str | None = None

    # Phase 3 Plan 03-02 SSO-01 (D-V3-Phase3-B) — Hub con cache lifecycle
    # 1h refresh interval matching Cache-Control max-age=3600 ở Plan 03-01.
    # 24h hard limit (86400s): nếu cached value > limit → 503 JWKS_STALE
    # envelope cho mọi JWT verify (R-V3-5 fail-loud delayed). Override qua env
    # JWKS_REFRESH_INTERVAL + JWKS_MAX_STALE_SECONDS nếu test rotation nhanh.
    jwks_refresh_interval: int = 3600
    jwks_max_stale_seconds: int = 86400

    # Phase 3 Plan 03-04 SSO-02 (D-V3-Phase3-G) — Hub con redirect login/refresh.
    # Base URL central cho 307 redirect (vd "http://python-api-central:8080").
    # Hub con required (model_validator `_enforce_central_url_for_hub` enforce);
    # central None OK. Tách khỏi `central_jwks_url` vì base URL dùng cho N
    # endpoint khác login/refresh (Phase 5 PROXY-02 frontend cũng consume).
    # docker-compose 3 hub con set env
    #   CENTRAL_URL=http://python-api-central:8080
    central_url: str | None = None

    # File storage
    file_store_dir: Path = Path("./file_store")

    # RAG (Phase 4-7 wiring — pin dim 1536 cho R1 pgvector HNSW index)
    rag_embedding_provider: str = "openai"
    rag_embedding_model: str = "text-embedding-3-small"
    rag_embedding_dim: int = 1536
    rag_llm_provider: str = "openai"
    # Model OpenAI — dùng khi rag_llm_provider != "gemini".
    rag_llm_model: str = "gpt-4o-mini"
    # Model Gemini — field RIÊNG, dùng khi rag_llm_provider == "gemini".
    # Tách khỏi rag_llm_model để rag-config đổi model Gemini KHÔNG ghi đè model
    # OpenAI (xem rag_config_service._apply_runtime / load_persisted_into_runtime).
    rag_gemini_llm_model: str = "gemini-2.5-flash"

    # External keys (Phase 7)
    openai_api_key: str = "sk-replace-me"
    gemini_api_key: str = "replace-me"

    # MCP ↔ API shared secret (Phase 8.3 per-user pre-registered OAuth add-on).
    # MCP service gửi `Authorization: Bearer <token>` khi gọi
    # `/api/internal/mcp/clients/{id}`. Endpoint internal trả 503 nếu rỗng
    # (chưa configured) — fail-closed thay vì silent allow.
    mcp_internal_token: str = ""

    # Settings encryption (Phase 5)
    aes_key: str = "replace-with-32-byte-base64-key"

    # Audit logger (Phase 5 AUX-01 — asyncio.Queue batch flush)
    audit_batch_size: int = 128
    audit_flush_interval_seconds: float = 2.0
    audit_queue_max_size: int = 10000
    # Rate limit (Phase 5 AUX-03 — slowapi; Plan 05-02 consume)
    rate_limit_search_per_minute: int = 100
    rate_limit_upload_per_minute: int = 30
    rate_limit_audit_logs_per_minute: int = 60
    rate_limit_enabled: bool = True

    # CORS (Phase 3 wire vào middleware — Phase 1 đã load + expose)
    # NoDecode: pydantic-settings v2 mặc định JSON-decode complex type → CSV
    # `http://a:5173,http://b:5173` raise SettingsError. NoDecode để raw string
    # đi thẳng vào `_parse_csv` validator (mode="before").
    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    @field_validator("hub_name", mode="after")
    @classmethod
    def _validate_hub_name(cls, v: str) -> str:
        """Regex format + reserved blacklist (FACTOR-04 Plan 02-05).

        Pattern `^[a-z][a-z0-9_]{0,15}$`:
        - lowercase a-z bắt đầu (KHÔNG digit/underscore — Postgres identifier
          khuyến nghị start với letter để khỏi quote)
        - body 0-15 char a-z0-9 underscore
        - max total = 16 char (medinet_hub_<name> = 12 + 16 = 28 char < 63 limit)

        Reserved blacklist: 6 name collide Postgres system DB / role (xem
        RESERVED_HUB_NAMES docstring module-level).

        Reject:
        - empty string → ValueError (regex không match)
        - uppercase ("Yte") → ValueError
        - hyphen ("phap-che") → ValueError
        - starting digit ("1hub") → ValueError
        - starting underscore ("_hub") → ValueError
        - > 16 char ("very_long_hub_name") → ValueError
        - reserved ("postgres", "cocoindex", ...) → ValueError

        Threat model cover:
        - T-02-05-01 Tampering env HUB_NAME special char → regex reject pre-DB-create
        - T-02-05-02 Privilege confuse hub_name=medinet/postgres → blacklist reject
        - T-02-05-03 DoS hub_name 100-char → regex max 16 char reject
        """
        if not re.fullmatch(r"^[a-z][a-z0-9_]{0,15}$", v):
            raise ValueError(
                f"hub_name invalid format: {v!r}. Pattern required: "
                f"^[a-z][a-z0-9_]{{0,15}}$ (lowercase a-z first char, max 16 "
                f"char total, a-z0-9_ rest — KHÔNG hyphen/uppercase/start-digit)."
            )
        if v in RESERVED_HUB_NAMES:
            raise ValueError(
                f"hub_name reserved: {v!r}. 6 reserved names collide Postgres "
                f"system DB / role medinet: {sorted(RESERVED_HUB_NAMES)}."
            )
        return v

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _parse_csv(cls, v: str | list[str]) -> list[str]:
        """Parse "a,b,c" → ["a","b","c"]; cho phép pass list trực tiếp."""
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @field_validator("cors_allowed_origins", mode="after")
    @classmethod
    def _no_lan_in_prod(cls, v: list[str], info: ValidationInfo) -> list[str]:
        """Reject LAN/localhost origin trong production env (P12 mitigation).

        Nếu deploy production mà CORS list lọt `http://192.168.x.x` hoặc `localhost`,
        attacker trong cùng LAN có thể bypass CORS gọi API → leak credentials.
        Fail-fast ngay startup, KHÔNG defer runtime.

        Dev/staging chấp nhận localhost — chỉ reject khi `app_env=="production"`.
        """
        if info.data.get("app_env") != "production":
            return v
        forbidden_patterns = [
            r"localhost",
            r"127\.0\.0\.1",
            r"0\.0\.0\.0",
            r"192\.168\.",
            r"\b10\.",
            r"172\.(1[6-9]|2[0-9]|3[01])\.",
        ]
        for origin in v:
            for pat in forbidden_patterns:
                if re.search(pat, origin):
                    raise ValueError(
                        f"Production cấm CORS origin LAN/localhost: {origin!r} "
                        f"(match pattern {pat!r}). P12 mitigation."
                    )
        return v

    @model_validator(mode="after")
    def _enforce_hub_dsn_match(self) -> Settings:
        """E-V3-3 enforce — `hub_name` phải khớp database name trong DSN.

        Chống: deploy với `HUB_NAME=yte` nhưng `DATABASE_URL` trỏ
        `medinet_hub_duoc` (cross-hub) hoặc tệ hơn `medinet_central`
        (hub con đọc/ghi aggregated data) → process truy cập sai data
        hub. Fail-fast ở startup, KHÔNG defer runtime.

        Quy ước DSN suffix:
        - `hub_name == "central"`  → DSN phải kết thúc `/medinet_central`
        - `hub_name == "<hub>"`    → DSN phải kết thúc `/medinet_hub_<hub>`

        Cho phép DSN query string (`?option=value`, vd `?sslmode=require`)
        — strip trước khi check suffix.

        Threat model cover: T-01-02-01 (Spoofing), T-01-02-02 (Info Disclosure),
        T-01-02-03 (EoP).
        """
        # Strip query string nếu có
        dsn_path = self.database_url.split("?", 1)[0].rstrip("/")
        expected_db = (
            "medinet_central"
            if self.hub_name == "central"
            else f"medinet_hub_{self.hub_name}"
        )
        if not dsn_path.endswith(f"/{expected_db}"):
            actual_db = dsn_path.rsplit("/", 1)[-1]
            raise ValueError(
                f"DSN mismatch hub_name: HUB_NAME={self.hub_name!r} yêu cầu "
                f"database {expected_db!r} nhưng DATABASE_URL trỏ "
                f"{actual_db!r}. E-V3-3 enforce — KHÔNG fallback central."
            )
        return self

    @model_validator(mode="after")
    def _enforce_central_jwks_url_for_hub(self) -> Settings:
        """Phase 3 Plan 03-02 SSO-01 (D-V3-Phase3-B) — Hub con required CENTRAL_JWKS_URL.

        Central (hub_name="central") tự có private.pem local → KHÔNG cần fetch.
        Hub con (yte/duoc/hcns/dynamic) PHẢI set CENTRAL_JWKS_URL trỏ central
        endpoint để JWKSCache.fetch_initial() blocking startup. Thiếu → boot fail
        ở Settings validation (ValidationError trước khi tới lifespan).

        Threat model:
        - T-03-02-01 Tampering — env thiếu CENTRAL_JWKS_URL → hub con boot OK
          nhưng mọi JWT verify trả 500 (chưa lifespan startup). Fail-fast ở
          validator tránh production bug câm lặng.
        """
        if self.hub_name != "central" and not self.central_jwks_url:
            raise ValueError(
                f"hub_name={self.hub_name!r} (hub con) yêu cầu CENTRAL_JWKS_URL "
                f"env var. Set CENTRAL_JWKS_URL=http://python-api-central:8080"
                f"/.well-known/jwks.json (xem docker-compose.yml 3 hub con block)."
            )
        return self

    @model_validator(mode="after")
    def _enforce_central_url_for_hub(self) -> Settings:
        """Phase 3 Plan 03-04 SSO-02 (D-V3-Phase3-G) — Hub con required CENTRAL_URL.

        Hub con (yte/duoc/hcns/dynamic) redirect POST /api/auth/login +
        /api/auth/refresh tới central qua 307 Location header (D-V3-Phase3-G
        LOCKED — browser auto-follow + preserve POST method + body RFC 7231).
        Thiếu CENTRAL_URL → boot fail-fast ở validator (KHÔNG defer runtime
        router handler — tránh silent failure mọi login request trả 503 silent).

        Tách field khỏi `central_jwks_url`:
        - `central_jwks_url` = full URL endpoint `/.well-known/jwks.json`.
        - `central_url` = base URL không suffix — build N URL khác (login,
          refresh, future endpoints).

        Threat model:
        - T-03-04-01 Spoofing — operator KHÔNG set CENTRAL_URL → hub con boot
          OK nhưng login → 503/500 silent. Fail-fast validator chống production
          deploy bug câm lặng.
        - T-03-04-04 DoS — thiếu CENTRAL_URL → mọi login locked out. Validator
          fail-fast hub con KHÔNG start được nếu thiếu — KHÔNG silent failure.
        """
        if self.hub_name != "central" and not self.central_url:
            raise ValueError(
                f"hub_name={self.hub_name!r} (hub con) yêu cầu CENTRAL_URL "
                f"env var. Set CENTRAL_URL=http://python-api-central:8080 "
                f"(xem docker-compose.yml 3 hub con block — Plan 03-04 SSO-02)."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Singleton settings instance — cache để tránh re-parse env mỗi lần gọi."""
    return Settings()


def resolve_database_url(base_dsn: str, hub_name: str) -> str:
    """Resolve DSN central → DSN hub con bằng cách thay tên database cuối path.

    Dùng cho:
    - `make migrate-all` loop apply Alembic per-hub (Plan 03 consume qua
      `-x hub=<name>`).
    - `make hub-init HUB=<name>` dynamic add hub (Plan 05).

    Logic:
    - `hub_name == "central"` → trả nguyên `base_dsn` (no-op).
    - `hub_name == "<hub>"`   → thay segment `medinet_central` thành
      `medinet_hub_<hub>`.

    Preserve query string (`?option=value`) nếu có.

    Args:
        base_dsn: DSN trỏ `medinet_central`
            (vd ``postgresql+asyncpg://u:p@h:5432/medinet_central``).
        hub_name: ``"central" | "yte" | "duoc" | "hcns"``.

    Returns:
        DSN đã resolve — `medinet_central` thay bằng
        `medinet_hub_<name>` (nếu `hub_name != "central"`).

    Raises:
        ValueError: `base_dsn` không kết thúc bằng `/medinet_central`
            → caller dùng sai input (T-01-02-04 Tampering mitigation).
    """
    if hub_name == "central":
        return base_dsn
    # Strip query string trước khi thay segment để giữ nguyên query.
    if "?" in base_dsn:
        path_part, query_part = base_dsn.split("?", 1)
        query_suffix = f"?{query_part}"
    else:
        path_part, query_suffix = base_dsn, ""
    if not path_part.endswith("/medinet_central"):
        raise ValueError(
            f"base_dsn phải kết thúc bằng '/medinet_central' để resolve "
            f"per-hub; nhận: {path_part!r}"
        )
    new_path = path_part[: -len("medinet_central")] + f"medinet_hub_{hub_name}"
    return new_path + query_suffix
