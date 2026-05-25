"""Email service — wrapper smtplib stdlib gửi email transactional.

Hai use case hiện tại:
- Welcome email khi admin tạo user mới (POST /api/users) — gửi password tạm.
- Reset password email khi admin reset (POST /api/users/:id/reset-password) —
  gửi password mới.

Kiến trúc:
- `load_smtp_config(db)` query 7 SMTP key + 2 system key + NOTIFY_EMAIL_ENABLED
  từ bảng `settings`. Return `None` nếu chưa cấu hình đủ HOẶC user tắt
  NOTIFY_EMAIL_ENABLED. KHÔNG raise — gọi check `is None` trước khi enqueue.
- `send_email_sync` dùng `smtplib.SMTP` stdlib thuần (KHÔNG cần dep mới
  aiosmtplib). Auto-pick SMTP_SSL khi port 465, STARTTLS khi use_tls=true +
  port khác.
- `send_welcome_email` / `send_reset_password_email` async wrapper: chạy
  send sync trong `asyncio.to_thread()` để KHÔNG block event loop. Pattern
  này hợp với FastAPI BackgroundTasks (chạy sau response, KHÔNG block client).
- Fail-quiet: log warning khi send fail, KHÔNG raise lên BackgroundTask
  (memory `project_fastapi_bgtask_commit` + `feedback_surface_error_message`
  — user đã thấy modal password 1 lần ở UI, email fail KHÔNG nên đảo ngược
  create user thành công).

Bảo mật:
- Plaintext password CHỈ tồn tại trong scope BackgroundTask + email body —
  KHÔNG log password vào logger (T-05-04-03 carry forward Plan 05-04).
- SMTP password load từ DB qua `load_smtp_config` (raw, KHÔNG mask), pass
  vào dataclass `SmtpConfig` — KHÔNG log toàn bộ dataclass (__repr__ default
  sẽ leak password; dùng `repr=False` field cho password).
- Template HTML escape user-provided `name` qua `html.escape` (T-XSS — nếu
  future ai forward email → reader → user click link inject).
"""
from __future__ import annotations

import asyncio
import html
import json
import logging
import smtplib
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# 7 SMTP key + 3 key contextual (NOTIFY_EMAIL_ENABLED gate + SYSTEM_NAME/URL
# branding template). Subset của _DEFAULTS ở system_settings_service.
_SMTP_KEYS: tuple[str, ...] = (
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "SMTP_FROM_EMAIL",
    "SMTP_FROM_NAME",
    "SMTP_USE_TLS",
    "NOTIFY_EMAIL_ENABLED",
    "SYSTEM_NAME",
    "SYSTEM_URL",
)


@dataclass(frozen=True)
class SmtpConfig:
    """Snapshot SMTP config — pass vào BackgroundTask, KHÔNG share DB session."""

    host: str
    port: int
    username: str
    # `repr=False` chặn __repr__ default leak password vào log.
    password: str = field(repr=False)
    from_email: str
    from_name: str
    use_tls: bool
    system_name: str
    system_url: str


def _parse_jsonb(raw: Any) -> Any:
    """Raw JSONB column → Python value (carry forward system_settings_service)."""
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return raw
    return raw


async def _load_smtp_stored(db: AsyncSession) -> dict[str, str]:
    """Đọc raw SMTP key từ bảng `settings`. Helper share giữa load_smtp_config
    (auto-send welcome/reset) + build_smtp_config_from_overrides (test endpoint).
    """
    rows = (
        await db.execute(
            text("SELECT key, value FROM settings WHERE key = ANY(:keys)"),
            {"keys": list(_SMTP_KEYS)},
        )
    ).fetchall()
    return {row[0]: str(_parse_jsonb(row[1])) for row in rows}


def _build_smtp_config(stored: dict[str, str]) -> SmtpConfig | None:
    """Build SmtpConfig từ dict raw key/value. Return None nếu thiếu HOST/FROM."""
    host = stored.get("SMTP_HOST", "").strip()
    from_email = stored.get("SMTP_FROM_EMAIL", "").strip()
    if not host or not from_email:
        return None
    try:
        port = int(stored.get("SMTP_PORT", "587"))
    except ValueError:
        port = 587
    return SmtpConfig(
        host=host,
        port=port,
        username=stored.get("SMTP_USERNAME", "").strip(),
        password=stored.get("SMTP_PASSWORD", ""),
        from_email=from_email,
        from_name=stored.get("SMTP_FROM_NAME", "Medinet Wiki").strip()
        or "Medinet Wiki",
        use_tls=stored.get("SMTP_USE_TLS", "true").lower() == "true",
        system_name=stored.get("SYSTEM_NAME", "Medinet Wiki").strip()
        or "Medinet Wiki",
        system_url=stored.get("SYSTEM_URL", "").strip(),
    )


async def load_smtp_config(
    db: AsyncSession, *, require_enabled: bool = True
) -> SmtpConfig | None:
    """Load SMTP config từ bảng `settings`. Return None nếu chưa đủ hoặc tắt.

    Điều kiện return None:
    - `require_enabled=True` (mặc định) + NOTIFY_EMAIL_ENABLED != 'true' (admin
      tắt notify email ở tab Thông báo). Test endpoint pass False để cho phép
      test khi notify chưa bật.
    - SMTP_HOST hoặc SMTP_FROM_EMAIL rỗng (chưa cấu hình tối thiểu).

    Trả None để router skip enqueue silently (KHÔNG raise — admin có thể chủ
    ý tắt SMTP, KHÔNG phải lỗi).
    """
    stored = await _load_smtp_stored(db)
    if require_enabled and stored.get("NOTIFY_EMAIL_ENABLED", "true").lower() != "true":
        return None
    return _build_smtp_config(stored)


async def build_smtp_config_with_overrides(
    db: AsyncSession, overrides: dict[str, str] | None
) -> SmtpConfig | None:
    """Build SmtpConfig từ overrides (form FE chưa save) + DB fallback.

    Pattern preserve-on-empty: nếu overrides có key nhưng value rỗng (hoặc value
    là mask `********` cho SMTP_PASSWORD), dùng giá trị DB. Giúp admin test
    SMTP với cấu hình form CHƯA save mà KHÔNG phải gõ lại password.

    Trả None nếu sau merge vẫn thiếu SMTP_HOST hoặc SMTP_FROM_EMAIL.
    """
    stored = await _load_smtp_stored(db)
    if overrides:
        for key in _SMTP_KEYS:
            if key not in overrides:
                continue
            value = overrides[key]
            # SMTP_PASSWORD: rỗng / mask "********" → giữ DB (preserve-on-empty).
            if key == "SMTP_PASSWORD" and value in ("", "********"):
                continue
            stored[key] = value
    return _build_smtp_config(stored)


def send_test_email(config: SmtpConfig, *, to_email: str) -> bool:
    """Gửi test email synchronous — admin click "Test gửi email" trong Settings.

    Subject + body cố định ngắn gọn tiếng Việt. KHÔNG escape XSS phức tạp vì
    nội dung do server kiểm soát + không có user input nguy hiểm (chỉ
    system_name + recipient email — đều đã đi qua sanitization của Pydantic).
    """
    safe_system = html.escape(config.system_name)
    safe_to = html.escape(to_email)
    text_body = (
        f"Đây là email test từ {config.system_name}.\n\n"
        f"Nếu bạn nhận được email này, cấu hình SMTP đã hoạt động đúng:\n"
        f"  - Host: {config.host}:{config.port}\n"
        f"  - From: {config.from_email}\n"
        f"  - To: {to_email}\n"
        f"  - STARTTLS: {'có' if config.use_tls else 'không'}\n\n"
        f"-- {config.system_name}"
    )
    html_body = f"""\
<!DOCTYPE html>
<html lang="vi">
  <body style="font-family: -apple-system, Segoe UI, Roboto, sans-serif; line-height: 1.5; color: #1e293b;">
    <h2 style="color: #6366f1;">✓ Test SMTP thành công</h2>
    <p>Đây là email test từ <strong>{safe_system}</strong>.</p>
    <p>Nếu bạn nhận được email này, cấu hình SMTP đã hoạt động đúng.</p>
    <table style="border-collapse: collapse; margin: 16px 0; font-size: 14px;">
      <tr><td style="padding: 6px 12px; background: #f1f5f9; border: 1px solid #e2e8f0;">Host</td><td style="padding: 6px 12px; border: 1px solid #e2e8f0;"><code>{html.escape(config.host)}:{config.port}</code></td></tr>
      <tr><td style="padding: 6px 12px; background: #f1f5f9; border: 1px solid #e2e8f0;">From</td><td style="padding: 6px 12px; border: 1px solid #e2e8f0;"><code>{html.escape(config.from_email)}</code></td></tr>
      <tr><td style="padding: 6px 12px; background: #f1f5f9; border: 1px solid #e2e8f0;">To</td><td style="padding: 6px 12px; border: 1px solid #e2e8f0;"><code>{safe_to}</code></td></tr>
      <tr><td style="padding: 6px 12px; background: #f1f5f9; border: 1px solid #e2e8f0;">STARTTLS</td><td style="padding: 6px 12px; border: 1px solid #e2e8f0;">{'có' if config.use_tls else 'không'}</td></tr>
    </table>
    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;" />
    <p style="font-size: 12px; color: #64748b;">Email gửi tự động từ {safe_system}. Vui lòng KHÔNG trả lời email này.</p>
  </body>
</html>
"""
    return send_email_sync(
        config,
        to_email=to_email,
        subject=f"[{config.system_name}] Test SMTP",
        html_body=html_body,
        text_body=text_body,
    )


def _smtp_send_raw(config: SmtpConfig, msg: MIMEMultipart) -> None:
    """Low-level smtplib send — raise raw exception cho caller xử lý diagnostics.

    Tách khỏi send_email_sync (fail-quiet) để endpoint test có thể catch
    từng class exception và trả message tiếng Việt cụ thể.
    """
    if config.port == 465:
        with smtplib.SMTP_SSL(config.host, config.port, timeout=15) as smtp:
            if config.username and config.password:
                smtp.login(config.username, config.password)
            smtp.send_message(msg)
        return
    with smtplib.SMTP(config.host, config.port, timeout=15) as smtp:
        smtp.ehlo()
        if config.use_tls:
            smtp.starttls()
            smtp.ehlo()
        if config.username and config.password:
            smtp.login(config.username, config.password)
        smtp.send_message(msg)


def send_test_email_with_diagnostics(
    config: SmtpConfig, *, to_email: str
) -> tuple[bool, str]:
    """Variant của send_test_email — trả về (success, error_message).

    KHÔNG dùng send_email_sync chung (vốn fail-quiet log warning) — endpoint
    test cần thông báo lý do fail cho admin (DNS / auth / connection refused).

    LƯU Ý: error message return cho FE KHÔNG được leak password — exc.__str__
    của smtplib KHÔNG chứa credential, nhưng vẫn defensive strip.
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[{config.system_name}] Test SMTP"
    msg["From"] = formataddr((config.from_name, config.from_email))
    msg["To"] = to_email
    safe_system = html.escape(config.system_name)
    safe_to = html.escape(to_email)
    text_body = (
        f"Đây là email test từ {config.system_name}.\n\n"
        f"Nếu bạn nhận được email này, cấu hình SMTP đã hoạt động đúng:\n"
        f"  - Host: {config.host}:{config.port}\n"
        f"  - From: {config.from_email}\n"
        f"  - To: {to_email}\n"
        f"  - STARTTLS: {'có' if config.use_tls else 'không'}\n\n"
        f"-- {config.system_name}"
    )
    html_body = f"""\
<!DOCTYPE html>
<html lang="vi">
  <body style="font-family: -apple-system, Segoe UI, Roboto, sans-serif; line-height: 1.5; color: #1e293b;">
    <h2 style="color: #6366f1;">✓ Test SMTP thành công</h2>
    <p>Đây là email test từ <strong>{safe_system}</strong>.</p>
    <p>Nếu bạn nhận được email này, cấu hình SMTP đã hoạt động đúng.</p>
    <p><code>To: {safe_to}</code></p>
  </body>
</html>
"""
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        _smtp_send_raw(config, msg)
    except smtplib.SMTPAuthenticationError as exc:
        return False, f"Sai username/password SMTP ({exc.smtp_code}). Kiểm tra credential."
    except smtplib.SMTPConnectError as exc:
        return False, f"Không kết nối được {config.host}:{config.port} ({exc})."
    except smtplib.SMTPRecipientsRefused:
        return False, f"Server từ chối recipient '{to_email}'. Kiểm tra địa chỉ email."
    except smtplib.SMTPSenderRefused as exc:
        return False, f"Server từ chối From '{config.from_email}' ({exc.smtp_code})."
    except smtplib.SMTPException as exc:
        return False, f"SMTP error: {exc}"
    except TimeoutError:
        return False, f"Timeout kết nối {config.host}:{config.port} sau 15s."
    except OSError as exc:
        return False, f"Lỗi mạng / DNS: {exc}"

    logger.info(
        "email_test_sent: host=%s to=%s",
        config.host,
        to_email,
    )
    return True, "OK"


def send_email_sync(
    config: SmtpConfig,
    *,
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str,
) -> bool:
    """Sync send qua smtplib stdlib. Fail-quiet log warning, return False khi fail.

    - Port 465 → SMTP_SSL implicit TLS từ đầu.
    - Port khác (587/25/...) + use_tls → STARTTLS sau EHLO.
    - username/password rỗng → skip login (cho phép SMTP relay open của local
      MTA / staging server).

    Timeout 15s — chặn hang nếu SMTP server unreachable (BackgroundTask vẫn
    bị hold trong threadpool worker; 15s là cap acceptable).
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((config.from_name, config.from_email))
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if config.port == 465:
            with smtplib.SMTP_SSL(config.host, config.port, timeout=15) as smtp:
                if config.username and config.password:
                    smtp.login(config.username, config.password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(config.host, config.port, timeout=15) as smtp:
                smtp.ehlo()
                if config.use_tls:
                    smtp.starttls()
                    smtp.ehlo()
                if config.username and config.password:
                    smtp.login(config.username, config.password)
                smtp.send_message(msg)
    except (OSError, smtplib.SMTPException) as exc:
        # OSError cover socket timeout, DNS fail, connection refused.
        # SMTPException cover auth fail, recipient refused, server error.
        # KHÔNG log password / smtp credential — chỉ host + to_email + exc.
        logger.warning(
            "email_send_failed: host=%s to=%s subject=%s err=%s",
            config.host,
            to_email,
            subject,
            exc,
        )
        return False

    logger.info(
        "email_sent: host=%s to=%s subject=%s",
        config.host,
        to_email,
        subject,
    )
    return True


def _render_welcome_email(
    config: SmtpConfig, *, name: str, email: str, password: str
) -> tuple[str, str]:
    """Render (html, plaintext) welcome email — tiếng Việt, escape XSS."""
    safe_name = html.escape(name or email)
    safe_email = html.escape(email)
    safe_system = html.escape(config.system_name)
    login_url = config.system_url or "(URL hệ thống chưa cấu hình)"
    safe_url = html.escape(login_url)

    text_body = (
        f"Chào {name or email},\n\n"
        f"Tài khoản của bạn trên {config.system_name} đã được tạo.\n\n"
        f"Email đăng nhập: {email}\n"
        f"Mật khẩu tạm: {password}\n\n"
        f"Vui lòng đăng nhập tại {login_url} và đổi mật khẩu ngay lần đầu.\n\n"
        f"-- {config.system_name}"
    )
    html_body = f"""\
<!DOCTYPE html>
<html lang="vi">
  <body style="font-family: -apple-system, Segoe UI, Roboto, sans-serif; line-height: 1.5; color: #1e293b;">
    <h2 style="color: #6366f1;">Chào {safe_name},</h2>
    <p>Tài khoản của bạn trên <strong>{safe_system}</strong> đã được tạo.</p>
    <table style="border-collapse: collapse; margin: 16px 0;">
      <tr>
        <td style="padding: 8px 16px; background: #f1f5f9; border: 1px solid #e2e8f0;">Email đăng nhập</td>
        <td style="padding: 8px 16px; border: 1px solid #e2e8f0;"><code>{safe_email}</code></td>
      </tr>
      <tr>
        <td style="padding: 8px 16px; background: #f1f5f9; border: 1px solid #e2e8f0;">Mật khẩu tạm</td>
        <td style="padding: 8px 16px; border: 1px solid #e2e8f0;"><code style="background: #fef3c7; padding: 2px 6px; border-radius: 4px;">{html.escape(password)}</code></td>
      </tr>
    </table>
    <p>Vui lòng đăng nhập tại <a href="{safe_url}" style="color: #6366f1;">{safe_url}</a> và <strong>đổi mật khẩu</strong> ngay lần đầu.</p>
    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;" />
    <p style="font-size: 12px; color: #64748b;">Email gửi tự động từ {safe_system}. Vui lòng KHÔNG trả lời email này.</p>
  </body>
</html>
"""
    return html_body, text_body


def _render_reset_password_email(
    config: SmtpConfig, *, name: str, email: str, password: str
) -> tuple[str, str]:
    """Render (html, plaintext) reset password email — tiếng Việt, escape XSS."""
    safe_name = html.escape(name or email)
    safe_email = html.escape(email)
    safe_system = html.escape(config.system_name)
    login_url = config.system_url or "(URL hệ thống chưa cấu hình)"
    safe_url = html.escape(login_url)

    text_body = (
        f"Chào {name or email},\n\n"
        f"Mật khẩu tài khoản của bạn trên {config.system_name} đã được "
        f"quản trị viên reset.\n\n"
        f"Email đăng nhập: {email}\n"
        f"Mật khẩu mới: {password}\n\n"
        f"Vui lòng đăng nhập tại {login_url} và đổi mật khẩu ngay.\n\n"
        f"Nếu bạn KHÔNG yêu cầu reset, vui lòng liên hệ quản trị viên ngay "
        f"để bảo vệ tài khoản.\n\n"
        f"-- {config.system_name}"
    )
    html_body = f"""\
<!DOCTYPE html>
<html lang="vi">
  <body style="font-family: -apple-system, Segoe UI, Roboto, sans-serif; line-height: 1.5; color: #1e293b;">
    <h2 style="color: #6366f1;">Chào {safe_name},</h2>
    <p>Mật khẩu tài khoản của bạn trên <strong>{safe_system}</strong> vừa được <strong>quản trị viên reset</strong>.</p>
    <table style="border-collapse: collapse; margin: 16px 0;">
      <tr>
        <td style="padding: 8px 16px; background: #f1f5f9; border: 1px solid #e2e8f0;">Email đăng nhập</td>
        <td style="padding: 8px 16px; border: 1px solid #e2e8f0;"><code>{safe_email}</code></td>
      </tr>
      <tr>
        <td style="padding: 8px 16px; background: #f1f5f9; border: 1px solid #e2e8f0;">Mật khẩu mới</td>
        <td style="padding: 8px 16px; border: 1px solid #e2e8f0;"><code style="background: #fef3c7; padding: 2px 6px; border-radius: 4px;">{html.escape(password)}</code></td>
      </tr>
    </table>
    <p>Vui lòng đăng nhập tại <a href="{safe_url}" style="color: #6366f1;">{safe_url}</a> và <strong>đổi mật khẩu</strong> ngay.</p>
    <div style="margin: 16px 0; padding: 12px 16px; background: #fef2f2; border-left: 4px solid #ef4444; border-radius: 4px;">
      <p style="margin: 0; font-size: 13px; color: #991b1b;">
        <strong>Nếu bạn KHÔNG yêu cầu reset</strong>, hãy liên hệ quản trị viên ngay để bảo vệ tài khoản.
      </p>
    </div>
    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;" />
    <p style="font-size: 12px; color: #64748b;">Email gửi tự động từ {safe_system}. Vui lòng KHÔNG trả lời email này.</p>
  </body>
</html>
"""
    return html_body, text_body


async def send_welcome_email(
    config: SmtpConfig,
    *,
    to_email: str,
    name: str,
    password: str,
) -> bool:
    """Async wrapper — chạy send sync trong threadpool, fail-quiet.

    Gọi từ FastAPI BackgroundTasks SAU khi service.create thành công +
    `load_smtp_config(db) is not None`.
    """
    subject = f"Chào mừng bạn đến với {config.system_name}"
    html_body, text_body = _render_welcome_email(
        config, name=name, email=to_email, password=password
    )
    return await asyncio.to_thread(
        send_email_sync,
        config,
        to_email=to_email,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
    )


async def send_reset_password_email(
    config: SmtpConfig,
    *,
    to_email: str,
    name: str,
    password: str,
) -> bool:
    """Async wrapper — chạy send sync trong threadpool, fail-quiet.

    Gọi từ FastAPI BackgroundTasks SAU khi service.reset_password thành công +
    `load_smtp_config(db) is not None`.
    """
    subject = f"[{config.system_name}] Mật khẩu của bạn đã được reset"
    html_body, text_body = _render_reset_password_email(
        config, name=name, email=to_email, password=password
    )
    return await asyncio.to_thread(
        send_email_sync,
        config,
        to_email=to_email,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
    )
