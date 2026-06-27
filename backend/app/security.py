"""Password hashing, JWT, and credential encryption helpers."""
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

import bcrypt
from cryptography.fernet import Fernet
from jose import JWTError, jwt

from .config import settings

_fernet = Fernet(settings.CREDENTIAL_KEY.encode())


# ----- Password hashing (bcrypt) -----
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


# ----- JWT -----
def _encode(data: dict, minutes: int) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(data: dict) -> str:
    """Short-lived access token. `data` should carry sub, is_admin, and tv."""
    payload = {**data, "type": "access"}
    return _encode(payload, settings.ACCESS_TOKEN_MINUTES)


def create_refresh_token(user_id: int, token_version: int) -> str:
    """Long-lived refresh token (H2). Carries the token_version for revocation."""
    return _encode({"sub": str(user_id), "tv": token_version, "type": "refresh"},
                   settings.REFRESH_TOKEN_DAYS * 24 * 60)


def issue_tokens(user) -> dict:
    """Issue an access+refresh pair for a user."""
    access = create_access_token({"sub": str(user.id), "is_admin": user.is_admin,
                                  "tv": user.token_version or 0})
    refresh = create_refresh_token(user.id, user.token_version or 0)
    return {"access_token": access, "refresh_token": refresh}


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


def create_evidence_token(app_id: int) -> str:
    """B2: short-lived, single-purpose token scoped to one application's evidence."""
    minutes = max(1, settings.EVIDENCE_URL_TTL // 60)
    return _encode({"purpose": "evidence", "app_id": int(app_id)}, minutes)


def verify_evidence_token(token: str, app_id: int) -> bool:
    payload = decode_access_token(token)
    return bool(payload and payload.get("purpose") == "evidence"
                and int(payload.get("app_id", -1)) == int(app_id))


# ----- Password reset tokens -----
def generate_reset_token() -> str:
    """Return a URL-safe one-time reset token (the raw value, shown once)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Tokens are stored hashed so the DB never holds the usable value."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ----- Byte encryption (Fernet) for PII at rest (resume files) -----
_PII_MAGIC = b"JBENC1:"  # marker so we can detect encrypted blobs vs legacy plaintext


def encrypt_bytes(data: bytes) -> bytes:
    return _PII_MAGIC + _fernet.encrypt(data)


def decrypt_bytes(blob: bytes) -> bytes:
    if not blob:
        return b""
    if blob.startswith(_PII_MAGIC):
        return _fernet.decrypt(blob[len(_PII_MAGIC):])
    return blob  # legacy/plaintext (pre-encryption uploads) — return as-is


# ----- Credential encryption (Fernet) -----
def encrypt_value(value: str) -> str:
    if not value:
        return ""
    return _fernet.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_value(token: str) -> str:
    if not token:
        return ""
    try:
        return _fernet.decrypt(token.encode("utf-8")).decode("utf-8")
    except Exception:
        return ""
