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


def test_not_registered_email_message(client):
    r = client.post("/api/auth/login",
                    json={"email": "nobody-here@example.com", "password": "whatever1"})
    assert r.status_code == 404
    assert "not registered" in str(r.json().get("error", "")).lower()


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
