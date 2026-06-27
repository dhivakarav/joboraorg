"""Email-verification-at-login + password-reset behavior.

Covers (per spec):
  - unverified login is blocked when REQUIRE_EMAIL_VERIFICATION is on
  - verified login is allowed
  - reset token expires
  - reset token is single-use
  - forgot-password does NOT leak whether an email exists
"""
import time
from datetime import datetime, timedelta

import pytest

from app.config import settings
from app.database import SessionLocal
from app.models import PasswordReset, User
from app.security import hash_password, hash_token, generate_reset_token


def _make_user(email=None, password="Passw0rd1", verified=False, status="approved"):
    email = email or f"u{int(time.time()*1e6)}@example.com"
    db = SessionLocal()
    try:
        u = User(full_name="Test U", email=email, hashed_password=hash_password(password),
                 status=status, is_admin=False, email_verified=verified)
        db.add(u); db.commit(); db.refresh(u)
        return u.id, email, password
    finally:
        db.close()


# ---- 1. unverified login blocked (gate ON) ------------------------------------
def test_unverified_login_blocked(client, monkeypatch):
    monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFICATION", True)
    _, email, pw = _make_user(verified=False)
    r = client.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 403
    assert "verify your email" in str(r.json().get("error", "")).lower()


# ---- 2. verified login allowed (gate ON) --------------------------------------
def test_verified_login_allowed(client, monkeypatch):
    monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFICATION", True)
    _, email, pw = _make_user(verified=True)
    r = client.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    assert r.json()["email_verified"] is True
    assert r.json().get("access_token")


def test_unknown_email_returns_same_401_as_wrong_password(client):
    # Both "email not found" and "wrong password" must return identical 401s
    # so attackers cannot enumerate which emails are registered.
    r_unknown = client.post("/api/auth/login",
                            json={"email": "nobody-here@example.com", "password": "whatever1"})
    assert r_unknown.status_code == 401
    assert "email or password" in str(r_unknown.json().get("error", "")).lower()


def test_resend_verification_is_generic(client):
    # Unknown email must return the same generic message (no leak).
    r = client.post("/api/auth/resend-verification", json={"email": "ghost@example.com"})
    assert r.status_code == 200
    assert "if that email is registered" in r.json()["message"].lower()


# ---- 3 & 4. reset token expiry + single-use -----------------------------------
def _issue_reset(user_id, expires_in_min=60):
    raw = generate_reset_token()
    db = SessionLocal()
    try:
        pr = PasswordReset(user_id=user_id, token_hash=hash_token(raw),
                           expires_at=datetime.utcnow() + timedelta(minutes=expires_in_min))
        db.add(pr); db.commit()
        return raw
    finally:
        db.close()


def test_reset_token_expired_rejected(client):
    uid, _, _ = _make_user()
    raw = _issue_reset(uid, expires_in_min=-1)   # already expired
    r = client.post("/api/auth/reset-password", json={"token": raw, "new_password": "NewPass1"})
    assert r.status_code == 400
    assert "invalid or has expired" in str(r.json().get("error", "")).lower()


def test_reset_token_single_use(client):
    uid, email, _ = _make_user()
    raw = _issue_reset(uid)
    # first use succeeds
    r1 = client.post("/api/auth/reset-password", json={"token": raw, "new_password": "NewPass1"})
    assert r1.status_code == 200, r1.text
    # second use of the same token is rejected
    r2 = client.post("/api/auth/reset-password", json={"token": raw, "new_password": "Another1"})
    assert r2.status_code == 400


# ---- 5. forgot-password does not reveal whether the email exists --------------
def test_forgot_password_no_email_enumeration(client, monkeypatch):
    # Make the dev token-exposure deterministic-off so responses are pure-generic.
    monkeypatch.setattr(settings, "EXPOSE_RESET_TOKEN", False)
    _, real_email, _ = _make_user()
    known = client.post("/api/auth/forgot-password", json={"email": real_email})
    unknown = client.post("/api/auth/forgot-password", json={"email": "no-such-user@example.com"})
    assert known.status_code == 200 and unknown.status_code == 200
    # Identical generic body in both cases — can't tell which email is registered.
    assert known.json() == unknown.json()
    assert "if an account exists" in known.json()["message"].lower()


# ---- silent-failure fix: SMTP failure is loudly logged, response stays generic --
def test_forgot_password_smtp_failure_logged_but_response_generic(client, monkeypatch, caplog):
    """A failed send (e.g. Resend 550) must still return the generic message (no
    enumeration leak) AND produce a clear ERROR log so the operator can see it."""
    import logging
    from app import notifications

    class _BoomSMTP:  # any use of the SMTP connection raises
        def __init__(self, *a, **k):
            raise notifications.smtplib.SMTPException("simulated 550 rejection")

    monkeypatch.setattr(notifications.smtplib, "SMTP", _BoomSMTP)
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.test")  # force the SMTP path
    monkeypatch.setattr(settings, "EXPOSE_RESET_TOKEN", False)
    _, email, _ = _make_user()  # real account → a send is attempted

    with caplog.at_level(logging.ERROR, logger="jobara.email"):
        r = client.post("/api/auth/forgot-password", json={"email": email})

    # User-facing: unchanged generic message (anti-enumeration preserved)
    assert r.status_code == 200
    assert r.json() == {
        "message": "If an account exists for that email, a reset link has been generated."
    }
    # Internal: a loud ERROR log was produced for the failed send
    errs = [rec for rec in caplog.records
            if rec.levelname == "ERROR" and "EMAIL SEND FAILED" in rec.getMessage()]
    assert errs, "expected a loud ERROR-level log for the failed email send"
    # ...and it must not contain the SMTP password
    assert all(settings.SMTP_PASSWORD not in rec.getMessage() for rec in caplog.records if settings.SMTP_PASSWORD)


# ---- item 3: signup succeeds even if the verification email send fails ----------
def test_signup_succeeds_when_verification_email_fails(client, monkeypatch):
    """A failed verification email must NOT roll back signup; the account is created,
    and the response carries a soft 'resend verification' hint."""
    from app import notifications

    class _BoomSMTP:
        def __init__(self, *a, **k):
            raise notifications.smtplib.SMTPException("simulated verification-email failure")

    monkeypatch.setattr(notifications.smtplib, "SMTP", _BoomSMTP)
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.test")  # force the SMTP path

    email = f"newsignup{int(time.time()*1e6)}@example.com"
    r = client.post("/api/auth/register", json={
        "full_name": "New User", "email": email, "password": "Passw0rd1"})

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["email"] == email                      # signup succeeded
    assert body.get("notice")                          # soft hint present
    assert "resend verification" in body["notice"].lower()

    # the account is actually created + queryable, still unverified
    db = SessionLocal()
    try:
        u = db.query(User).filter_by(email=email).first()
        assert u is not None
        assert u.email_verified is False
    finally:
        db.close()
