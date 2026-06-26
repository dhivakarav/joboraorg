"""Email notifications with a provider interface.

Production uses SMTP (set ``SMTP_HOST`` etc.). With no SMTP configured, emails
are logged to the console so flows still work end-to-end in dev. Sends are
best-effort and never raise into the request path.

Templated events: account pending, account approved, application submitted,
password reset. Keep bodies plain-text + minimal HTML for deliverability.
"""
from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from .config import settings

log = logging.getLogger("jobara.email")


def _send(to: str, subject: str, body: str, html: Optional[str] = None,
          raise_errors: bool = False) -> bool:
    """Send one email. Returns True on success, False on failure.

    Failures are LOUDLY logged at ERROR level (with the email type/subject,
    recipient, and the real exception) so a broken email setup is never silent —
    but the SMTP password is never logged. Never raises into the request path
    (callers like signup inspect the return value) unless raise_errors=True,
    which the admin SMTP diagnostic uses to surface the exact error.

    Supports both standard TLS modes: implicit SSL on port 465 (SMTPS, e.g.
    Gmail's SSL port) and STARTTLS on 587/25. Using STARTTLS code against a 465
    endpoint is a common misconfiguration that hangs until timeout.
    """
    if not to:
        log.error("EMAIL NOT SENT: empty recipient (subject=%r)", subject)
        return False
    if not settings.SMTP_HOST:
        # No SMTP configured → dev console fallback (clearly logged, not silent).
        log.info("email (console fallback, no SMTP_HOST) to=%s subject=%r", to, subject)
        print(f"\n[email→{to}] {subject}\n{'-' * 50}\n{body}\n{'-' * 50}\n")
        return True
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM
        msg["To"] = to
        msg.attach(MIMEText(body, "plain"))
        if html:
            msg.attach(MIMEText(html, "html"))
        port = int(settings.SMTP_PORT or 587)
        if port == 465:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, port, timeout=30)
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, port, timeout=30)
        with server:
            server.ehlo()
            if port != 465 and settings.SMTP_TLS:
                server.starttls()
                server.ehlo()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM, [to], msg.as_string())
        log.info("email sent to=%s subject=%r via=%s:%s", to, subject, settings.SMTP_HOST, port)
        return True
    except Exception as exc:
        # Loud + debuggable. `exc` carries the SMTP server response (e.g. a 550
        # rejection) but NEVER the password — we don't log settings.SMTP_PASSWORD.
        log.error("EMAIL SEND FAILED to=%s subject=%r from=%s host=%s: %s",
                  to, subject, settings.SMTP_FROM, settings.SMTP_HOST, exc)
        if raise_errors:
            raise
        return False


def smtp_diagnostic(to: str) -> dict:
    """Admin-only diagnostic: attempt a real SMTP send and report the exact
    outcome (and error type, never the password) plus the effective config.
    Lets ops confirm production email delivery without reading server logs."""
    cfg = {
        "host": settings.SMTP_HOST or None,
        "port": settings.SMTP_PORT,
        "tls": settings.SMTP_TLS,
        "user_set": bool(settings.SMTP_USER),
        "from": settings.SMTP_FROM,
        "mode": "console-fallback" if not settings.SMTP_HOST
        else ("SSL(465)" if int(settings.SMTP_PORT or 587) == 465 else "STARTTLS"),
    }
    try:
        ok = _send(to, "Jobara SMTP test",
                   "This is a Jobara SMTP diagnostic email. If you received it, "
                   "outbound email is working.", raise_errors=True)
        return {"ok": bool(ok), "error": None, "config": cfg}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "config": cfg}


# ---- Templated events ----
def account_pending(to: str, name: str):
    _send(
        to,
        "Welcome to Jobara — your account is pending approval",
        f"Hi {name},\n\nThanks for signing up for Jobara. Your account is pending "
        f"admin approval. You'll be able to sign in and start applying once it's "
        f"approved.\n\n— The Jobara team",
    )


def account_approved(to: str, name: str):
    _send(
        to,
        "Your Jobara account is approved 🎉",
        f"Hi {name},\n\nGood news — your Jobara account has been approved. "
        f"Sign in to upload your resume and start discovering matching jobs:\n"
        f"{settings.APP_BASE_URL}/login\n\n— The Jobara team",
    )


def application_recorded(to: str, name: str, job_title: str, company: str, status: str):
    _send(
        to,
        f"Application tracked: {job_title} at {company}",
        f"Hi {name},\n\nWe recorded your application for {job_title} at {company} "
        f"(status: {status}). Track all your applications in your Jobara dashboard:\n"
        f"{settings.APP_BASE_URL}/app/activity\n\n— The Jobara team",
    )


def password_reset(to: str, name: str, reset_link: str):
    mins = settings.RESET_TOKEN_TTL_MINUTES
    _send(
        to,
        "Reset your Jobara password",
        f"Hi {name},\n\nUse this link to set a new password (valid for {mins} minutes):\n"
        f"{settings.APP_BASE_URL}{reset_link}\n\nIf you didn't request this, ignore "
        f"this email.\n\n— The Jobara team",
    )
