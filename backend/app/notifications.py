"""Email notifications with a provider interface.

Production uses SMTP (set ``SMTP_HOST`` etc.). With no SMTP configured, emails
are logged to the console so flows still work end-to-end in dev. Sends are
best-effort and never raise into the request path.

Templated events: account pending, account approved, application submitted,
password reset. Keep bodies plain-text + minimal HTML for deliverability.
"""
from __future__ import annotations

import json
import logging
import re
import smtplib
import urllib.error
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from .config import settings

log = logging.getLogger("jobara.email")


def _bare_email(addr: str) -> str:
    """Extract the bare address from a possibly 'Name <email>' string."""
    m = re.search(r"<([^>]+)>", addr or "")
    return (m.group(1) if m else (addr or "")).strip()


def _http_post(url: str, headers: dict, payload: dict, ok_codes) -> bool:
    data = json.dumps(payload).encode()
    # A real User-Agent is REQUIRED: provider APIs behind Cloudflare (e.g.
    # api.resend.com) reject the default "Python-urllib/x" signature with HTTP
    # 403 "error code: 1010". Accept must be JSON.
    h = {"Content-Type": "application/json", "Accept": "application/json",
         "User-Agent": "Jobora/1.0 (+https://starconsulting.in)", **headers}
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status in ok_codes
    except urllib.error.HTTPError as e:
        # Surface the provider's actual error body (e.g. Resend's
        # "domain is not verified") instead of a bare 403 — never logs secrets.
        body = ""
        try:
            body = e.read().decode()[:400]
        except Exception:
            pass
        host = url.split("//", 1)[-1].split("/", 1)[0]
        raise RuntimeError(f"HTTP {e.code} from {host}: {body}") from None


def _active_email_provider() -> str:
    if settings.RESEND_API_KEY:
        return "resend"
    if settings.SENDGRID_API_KEY:
        return "sendgrid"
    if settings.BREVO_API_KEY:
        return "brevo"
    if settings.SMTP_HOST:
        return "smtp"
    return "console"


def _send_http_api(to: str, subject: str, body: str, html: Optional[str], raise_errors: bool):
    """Send via a transactional email HTTP API over port 443 — required where
    outbound SMTP is blocked (e.g. Render). Returns True/False, or None if no API
    provider is configured (caller falls back to SMTP/console)."""
    frm = settings.SMTP_FROM
    provider = _active_email_provider()
    if provider not in ("resend", "sendgrid", "brevo"):
        return None
    try:
        if provider == "resend":
            p = {"from": frm, "to": [to], "subject": subject, "text": body}
            if html:
                p["html"] = html
            ok = _http_post("https://api.resend.com/emails",
                            {"Authorization": f"Bearer {settings.RESEND_API_KEY}"}, p, (200, 201))
        elif provider == "sendgrid":
            content = [{"type": "text/plain", "value": body}]
            if html:
                content.append({"type": "text/html", "value": html})
            p = {"personalizations": [{"to": [{"email": to}]}],
                 "from": {"email": _bare_email(frm)}, "subject": subject, "content": content}
            ok = _http_post("https://api.sendgrid.com/v3/mail/send",
                            {"Authorization": f"Bearer {settings.SENDGRID_API_KEY}"}, p, (200, 202))
        else:  # brevo
            p = {"sender": {"email": _bare_email(frm)}, "to": [{"email": to}],
                 "subject": subject, "textContent": body}
            if html:
                p["htmlContent"] = html
            ok = _http_post("https://api.brevo.com/v3/smtp/email",
                            {"api-key": settings.BREVO_API_KEY}, p, (200, 201))
        log.info("email sent via %s API to=%s subject=%r", provider, to, subject)
        return ok
    except Exception as exc:
        log.error("EMAIL API SEND FAILED via=%s to=%s subject=%r: %s", provider, to, subject, exc)
        if raise_errors:
            raise
        return False


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
    # Prefer an HTTP API provider — these use port 443 and work where outbound
    # SMTP ports (25/465/587) are blocked, e.g. on Render.
    api = _send_http_api(to, subject, body, html, raise_errors)
    if api is not None:
        return api
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
    provider = _active_email_provider()
    cfg = {
        "provider": provider,
        "host": settings.SMTP_HOST or None,
        "port": settings.SMTP_PORT,
        "tls": settings.SMTP_TLS,
        "user_set": bool(settings.SMTP_USER),
        "from": settings.SMTP_FROM,
        "mode": provider if provider in ("resend", "sendgrid", "brevo")
        else ("console-fallback" if not settings.SMTP_HOST
              else ("SSL(465)" if int(settings.SMTP_PORT or 587) == 465 else "STARTTLS")),
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
