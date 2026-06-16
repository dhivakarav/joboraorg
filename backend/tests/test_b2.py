"""B2 automated tests — security, reliability, and confirmation-detection logic."""
import importlib

import pytest


# ---------------- Pure logic: Greenhouse confirmation detection (priority #3) ----------------
from app.adapters.greenhouse_submit import classify_confirmation


def test_confirmation_success_no_id_is_submitted():
    # Real Greenhouse often shows a thank-you page WITHOUT a numeric id.
    status, app_id, reason = classify_confirmation(
        "Thank you", "Thank you for applying to Stripe! We've received your application.")
    assert status == "Submitted" and app_id is None


def test_confirmation_with_id_is_verified():
    status, app_id, _ = classify_confirmation(
        "Application submitted", "Your application has been submitted. Confirmation number is GH-AB12CD34EF.")
    assert status == "Verified Submitted" and app_id == "GH-AB12CD34EF"


def test_captcha_is_failure_not_success():
    status, _, reason = classify_confirmation(
        "Verify", "Thank you for applying. Please complete the reCAPTCHA challenge.")
    assert status == "CAPTCHA Required"  # failure markers win over success


def test_validation_error_detected():
    status, _, reason = classify_confirmation("Apply", "There were errors with your submission.")
    assert status == "Failed" and "Validation" in reason


def test_ambiguous_is_failure():
    status, _, _ = classify_confirmation("Apply for role", "First name Last name Email Submit")
    assert status == "Failed"


# ---------------- PII encryption roundtrip (priority #5) ----------------
from app.security import decrypt_bytes, encrypt_bytes, create_evidence_token, verify_evidence_token


def test_encrypt_decrypt_bytes_roundtrip():
    data = b"%PDF-1.4 fake resume bytes"
    enc = encrypt_bytes(data)
    assert enc != data and enc.startswith(b"JBENC1:")
    assert decrypt_bytes(enc) == data


def test_decrypt_legacy_plaintext_passthrough():
    assert decrypt_bytes(b"plain old bytes") == b"plain old bytes"


# ---------------- Evidence token scoping (priority #4) ----------------
def test_evidence_token_is_scoped():
    tok = create_evidence_token(42)
    assert verify_evidence_token(tok, 42)
    assert not verify_evidence_token(tok, 99)         # wrong app
    assert not verify_evidence_token("garbage", 42)


# ---------------- Config fail-closed (B0 regression guard) ----------------
def test_prod_requires_secrets(monkeypatch):
    import app.config as cfg
    monkeypatch.setenv("JOBORA_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "")
    monkeypatch.setenv("CREDENTIAL_KEY", "")
    with pytest.raises(Exception):
        importlib.reload(cfg)
    # restore dev config for other tests
    monkeypatch.setenv("JOBORA_ENV", "development")
    importlib.reload(cfg)


# ---------------- API: error envelope (priority #1) ----------------
def test_error_envelope_has_request_id(client):
    r = client.get("/api/auth/me")  # no token → 401 envelope
    assert r.status_code == 401
    body = r.json()
    assert "error" in body and "request_id" in body


def test_validation_error_envelope(client):
    r = client.post("/api/auth/login", json={"email": "not-an-email"})  # missing password
    assert r.status_code == 422
    assert r.json().get("error") == "Invalid request"


# ---------------- API: auth + password policy + rate limit ----------------
def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_password_policy(client):
    assert client.post("/api/auth/register", json={"full_name": "W", "email": "w1@x.io", "password": "abc"}).status_code == 400
    assert client.post("/api/auth/register", json={"full_name": "W", "email": "w2@x.io", "password": "abcdefgh"}).status_code == 400
    assert client.post("/api/auth/register", json={"full_name": "Ok", "email": "ok@x.io", "password": "Str0ngPass1"}).status_code == 200


def test_jwt_refresh_and_revocation(client, admin_token):
    # login returns refresh; refresh works; logout revokes.
    lg = client.post("/api/auth/login", json={"email": "admin@jobara.io", "password": "AdminTest123"}).json()
    acc, ref = lg["access_token"], lg["refresh_token"]
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {acc}"}).status_code == 200
    nr = client.post("/api/auth/refresh", json={"refresh_token": ref})
    assert nr.status_code == 200 and nr.json()["access_token"]
    assert client.post("/api/auth/logout", headers={"Authorization": f"Bearer {acc}"}).status_code == 200
    # after logout the old access token is revoked
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {acc}"}).status_code == 401


def test_login_rate_limit(client):
    codes = [client.post("/api/auth/login", json={"email": "none@x.io", "password": "x"}).status_code
             for _ in range(8)]
    assert 429 in codes  # RL_LOGIN_PER_MIN=5 in test env
