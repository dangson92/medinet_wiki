"""Unit test email_service — load SMTP config + render template + send sync.

Pure Python test, KHÔNG cần Postgres/Redis/SMTP runtime. Mock
AsyncSession.execute cho `load_smtp_config`. Mock `smtplib.SMTP` +
`smtplib.SMTP_SSL` cho `send_email_sync`.

Coverage:
- `load_smtp_config`: 5 case (disabled / no host / no from / full / invalid port).
- `send_email_sync`: 5 case (starttls 587 / ssl 465 / skip login no creds /
  fail quiet SMTPException / fail quiet OSError).
- `_render_welcome_email` + `_render_reset_password_email`: XSS escape test.
- `send_welcome_email` + `send_reset_password_email` async wrapper: subject +
  delegation tới `asyncio.to_thread(send_email_sync, ...)`.
"""
from __future__ import annotations

import smtplib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.email_service import (
    SmtpConfig,
    _render_reset_password_email,
    _render_welcome_email,
    load_smtp_config,
    send_email_sync,
    send_reset_password_email,
    send_welcome_email,
)


def _make_session(rows: list[tuple[str, str]]) -> AsyncMock:
    """AsyncMock(AsyncSession) trả về list (key, jsonb_value) cho SELECT settings."""
    session = AsyncMock()
    result = MagicMock()
    result.fetchall.return_value = rows
    session.execute = AsyncMock(return_value=result)
    return session


def _make_config(**overrides: object) -> SmtpConfig:
    """Build SmtpConfig với sensible defaults cho test."""
    base = {
        "host": "smtp.example.com",
        "port": 587,
        "username": "user@example.com",
        "password": "secret",
        "from_email": "no-reply@example.com",
        "from_name": "Medinet Wiki",
        "use_tls": True,
        "system_name": "Medinet Wiki",
        "system_url": "https://wiki.example.com",
    }
    base.update(overrides)
    return SmtpConfig(**base)  # type: ignore[arg-type]


# ─── load_smtp_config ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_load_smtp_config_disabled_returns_none() -> None:
    """NOTIFY_EMAIL_ENABLED=false → None (admin chủ ý tắt notify email)."""
    session = _make_session(
        [
            ("NOTIFY_EMAIL_ENABLED", '"false"'),
            ("SMTP_HOST", '"smtp.example.com"'),
            ("SMTP_FROM_EMAIL", '"from@example.com"'),
        ]
    )
    config = await load_smtp_config(session)
    assert config is None


@pytest.mark.asyncio
async def test_load_smtp_config_no_host_returns_none() -> None:
    """SMTP_HOST rỗng → None (chưa cấu hình tối thiểu)."""
    session = _make_session(
        [
            ("NOTIFY_EMAIL_ENABLED", '"true"'),
            ("SMTP_HOST", '""'),
            ("SMTP_FROM_EMAIL", '"from@example.com"'),
        ]
    )
    config = await load_smtp_config(session)
    assert config is None


@pytest.mark.asyncio
async def test_load_smtp_config_no_from_email_returns_none() -> None:
    """SMTP_FROM_EMAIL rỗng → None (RFC 5322 yêu cầu From header)."""
    session = _make_session(
        [
            ("NOTIFY_EMAIL_ENABLED", '"true"'),
            ("SMTP_HOST", '"smtp.example.com"'),
            ("SMTP_FROM_EMAIL", '""'),
        ]
    )
    config = await load_smtp_config(session)
    assert config is None


@pytest.mark.asyncio
async def test_load_smtp_config_full_returns_config() -> None:
    """Cấu hình đầy đủ → SmtpConfig với đúng value."""
    session = _make_session(
        [
            ("NOTIFY_EMAIL_ENABLED", '"true"'),
            ("SMTP_HOST", '"smtp.gmail.com"'),
            ("SMTP_PORT", '"465"'),
            ("SMTP_USERNAME", '"bot@medinet.vn"'),
            ("SMTP_PASSWORD", '"app-password"'),
            ("SMTP_FROM_EMAIL", '"no-reply@medinet.vn"'),
            ("SMTP_FROM_NAME", '"Medinet Wiki Admin"'),
            ("SMTP_USE_TLS", '"false"'),
            ("SYSTEM_NAME", '"Medinet Wiki"'),
            ("SYSTEM_URL", '"https://wiki.medinet.vn"'),
        ]
    )
    config = await load_smtp_config(session)
    assert config is not None
    assert config.host == "smtp.gmail.com"
    assert config.port == 465
    assert config.username == "bot@medinet.vn"
    assert config.password == "app-password"
    assert config.from_email == "no-reply@medinet.vn"
    assert config.from_name == "Medinet Wiki Admin"
    assert config.use_tls is False
    assert config.system_name == "Medinet Wiki"
    assert config.system_url == "https://wiki.medinet.vn"


@pytest.mark.asyncio
async def test_load_smtp_config_invalid_port_falls_back_587() -> None:
    """SMTP_PORT không parse int được → fallback 587 default."""
    session = _make_session(
        [
            ("NOTIFY_EMAIL_ENABLED", '"true"'),
            ("SMTP_HOST", '"smtp.example.com"'),
            ("SMTP_PORT", '"not-a-number"'),
            ("SMTP_FROM_EMAIL", '"from@example.com"'),
        ]
    )
    config = await load_smtp_config(session)
    assert config is not None
    assert config.port == 587


@pytest.mark.asyncio
async def test_load_smtp_config_password_not_in_repr() -> None:
    """SmtpConfig __repr__ KHÔNG leak password (T-XX-XX Information Disclosure)."""
    session = _make_session(
        [
            ("NOTIFY_EMAIL_ENABLED", '"true"'),
            ("SMTP_HOST", '"smtp.example.com"'),
            ("SMTP_PORT", '"587"'),
            ("SMTP_PASSWORD", '"super-secret-leaked-into-logs"'),
            ("SMTP_FROM_EMAIL", '"from@example.com"'),
        ]
    )
    config = await load_smtp_config(session)
    assert config is not None
    assert "super-secret-leaked-into-logs" not in repr(config)


# ─── send_email_sync ───────────────────────────────────────────────────


def test_send_email_sync_starttls_pattern_port_587() -> None:
    """Port 587 + use_tls=True → SMTP() + ehlo() + starttls() + ehlo() + login()."""
    config = _make_config(port=587, use_tls=True)
    mock_smtp_instance = MagicMock()
    mock_smtp_cm = MagicMock()
    mock_smtp_cm.__enter__ = MagicMock(return_value=mock_smtp_instance)
    mock_smtp_cm.__exit__ = MagicMock(return_value=False)

    with patch("smtplib.SMTP", return_value=mock_smtp_cm) as mock_smtp:
        ok = send_email_sync(
            config,
            to_email="target@example.com",
            subject="Test",
            html_body="<p>hi</p>",
            text_body="hi",
        )
    assert ok is True
    mock_smtp.assert_called_once_with("smtp.example.com", 587, timeout=15)
    assert mock_smtp_instance.starttls.called
    mock_smtp_instance.login.assert_called_once_with(
        "user@example.com", "secret"
    )
    assert mock_smtp_instance.send_message.called


def test_send_email_sync_ssl_pattern_port_465() -> None:
    """Port 465 → SMTP_SSL implicit TLS, KHÔNG starttls (đã TLS từ đầu)."""
    config = _make_config(port=465, use_tls=False)
    mock_smtp_instance = MagicMock()
    mock_smtp_cm = MagicMock()
    mock_smtp_cm.__enter__ = MagicMock(return_value=mock_smtp_instance)
    mock_smtp_cm.__exit__ = MagicMock(return_value=False)

    with patch("smtplib.SMTP_SSL", return_value=mock_smtp_cm) as mock_ssl:
        ok = send_email_sync(
            config,
            to_email="target@example.com",
            subject="Test",
            html_body="<p>hi</p>",
            text_body="hi",
        )
    assert ok is True
    mock_ssl.assert_called_once_with("smtp.example.com", 465, timeout=15)
    assert not mock_smtp_instance.starttls.called
    mock_smtp_instance.login.assert_called_once()
    assert mock_smtp_instance.send_message.called


def test_send_email_sync_skips_login_when_no_credentials() -> None:
    """Username rỗng → skip login (SMTP relay open của local MTA)."""
    config = _make_config(username="", password="", use_tls=False)
    mock_smtp_instance = MagicMock()
    mock_smtp_cm = MagicMock()
    mock_smtp_cm.__enter__ = MagicMock(return_value=mock_smtp_instance)
    mock_smtp_cm.__exit__ = MagicMock(return_value=False)

    with patch("smtplib.SMTP", return_value=mock_smtp_cm):
        ok = send_email_sync(
            config,
            to_email="target@example.com",
            subject="Test",
            html_body="<p>hi</p>",
            text_body="hi",
        )
    assert ok is True
    assert not mock_smtp_instance.login.called
    assert mock_smtp_instance.send_message.called


def test_send_email_sync_fail_quiet_on_smtp_exception() -> None:
    """smtplib.SMTPAuthenticationError → return False, KHÔNG raise."""
    config = _make_config()
    mock_smtp_instance = MagicMock()
    mock_smtp_instance.login.side_effect = smtplib.SMTPAuthenticationError(
        535, b"auth failed"
    )
    mock_smtp_cm = MagicMock()
    mock_smtp_cm.__enter__ = MagicMock(return_value=mock_smtp_instance)
    mock_smtp_cm.__exit__ = MagicMock(return_value=False)

    with patch("smtplib.SMTP", return_value=mock_smtp_cm):
        ok = send_email_sync(
            config,
            to_email="target@example.com",
            subject="Test",
            html_body="<p>hi</p>",
            text_body="hi",
        )
    assert ok is False


def test_send_email_sync_fail_quiet_on_os_error() -> None:
    """Socket timeout / DNS fail → return False, KHÔNG raise."""
    config = _make_config()
    with patch("smtplib.SMTP", side_effect=OSError("Network unreachable")):
        ok = send_email_sync(
            config,
            to_email="target@example.com",
            subject="Test",
            html_body="<p>hi</p>",
            text_body="hi",
        )
    assert ok is False


# ─── Render template XSS escape ────────────────────────────────────────


def test_render_welcome_email_escapes_html_in_name() -> None:
    """User name có HTML/JS → escape qua html.escape (T-XSS)."""
    config = _make_config()
    html_body, text_body = _render_welcome_email(
        config,
        name="<script>alert(1)</script>",
        email="<img onerror=x>@example.com",
        password="P@ss<word>",
    )
    assert "<script>" not in html_body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html_body
    assert "&lt;img onerror=x&gt;" in html_body
    assert "P@ss&lt;word&gt;" in html_body
    # Plaintext KHÔNG cần escape (KHÔNG render HTML).
    assert "<script>alert(1)</script>" in text_body


def test_render_reset_password_email_escapes_html_in_name() -> None:
    """Same XSS escape cho reset template."""
    config = _make_config()
    html_body, _ = _render_reset_password_email(
        config,
        name="<b>bold</b>",
        email="test@example.com",
        password="new-pass",
    )
    assert "<b>bold</b>" not in html_body
    assert "&lt;b&gt;bold&lt;/b&gt;" in html_body


def test_render_welcome_email_includes_credentials_in_body() -> None:
    """Email body chứa email + password rõ ràng (mục đích chính)."""
    config = _make_config(system_name="Test System")
    html_body, text_body = _render_welcome_email(
        config,
        name="User",
        email="newuser@example.com",
        password="ABC123xyz",
    )
    assert "newuser@example.com" in text_body
    assert "ABC123xyz" in text_body
    assert "Test System" in text_body
    assert "newuser@example.com" in html_body
    assert "ABC123xyz" in html_body


# ─── Async wrapper send_welcome_email + send_reset_password_email ──────


@pytest.mark.asyncio
async def test_send_welcome_email_delegates_to_send_sync() -> None:
    """send_welcome_email gọi send_email_sync qua asyncio.to_thread với
    subject chứa system_name."""
    config = _make_config(system_name="My Wiki")
    with patch(
        "app.services.email_service.send_email_sync", return_value=True
    ) as mock_send:
        ok = await send_welcome_email(
            config,
            to_email="new@example.com",
            name="Test User",
            password="temp-pass-1234",
        )
    assert ok is True
    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args.kwargs
    assert call_kwargs["to_email"] == "new@example.com"
    assert "My Wiki" in call_kwargs["subject"]
    assert "Chào mừng" in call_kwargs["subject"]
    assert "temp-pass-1234" in call_kwargs["text_body"]


@pytest.mark.asyncio
async def test_send_reset_password_email_delegates_to_send_sync() -> None:
    """send_reset_password_email subject chứa system_name + từ khoá reset."""
    config = _make_config(system_name="My Wiki")
    with patch(
        "app.services.email_service.send_email_sync", return_value=True
    ) as mock_send:
        ok = await send_reset_password_email(
            config,
            to_email="user@example.com",
            name="Existing User",
            password="new-temp-9876",
        )
    assert ok is True
    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args.kwargs
    assert call_kwargs["to_email"] == "user@example.com"
    assert "My Wiki" in call_kwargs["subject"]
    assert "reset" in call_kwargs["subject"].lower()
    assert "new-temp-9876" in call_kwargs["text_body"]
