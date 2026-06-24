"""Per-user platform credentials (encrypted at rest).

Thin service over the ``platform_credentials`` table. Email/password are stored
as Fernet tokens (``security.encrypt_value``) and decrypted only in-process at
submit time. Callers never see another user's plaintext: ``get_plaintext`` is
scoped by ``user_id``.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from .models import PlatformCredential
from .security import decrypt_value, encrypt_value


def set_credentials(db: Session, user_id: int, platform: str,
                    username: str, password: str) -> PlatformCredential:
    """Create or update the (user, platform) credential. Encrypts on write."""
    cred = (db.query(PlatformCredential)
              .filter_by(user_id=user_id, platform=platform).first())
    if not cred:
        cred = PlatformCredential(user_id=user_id, platform=platform)
        db.add(cred)
    cred.encrypted_username = encrypt_value(username)
    cred.encrypted_password = encrypt_value(password)
    cred.is_active = True
    cred.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(cred)
    return cred


def has_credentials(db: Session, user_id: int, platform: str) -> bool:
    cred = (db.query(PlatformCredential)
              .filter_by(user_id=user_id, platform=platform, is_active=True).first())
    return bool(cred and cred.encrypted_username and cred.encrypted_password)


def get_plaintext(db: Session, user_id: int, platform: str) -> Optional[Tuple[str, str]]:
    """Return (username, password) decrypted, or None if not set. Scoped to user."""
    cred = (db.query(PlatformCredential)
              .filter_by(user_id=user_id, platform=platform, is_active=True).first())
    if not cred or not cred.encrypted_username:
        return None
    try:
        return decrypt_value(cred.encrypted_username), decrypt_value(cred.encrypted_password)
    except Exception:
        return None


def delete_credentials(db: Session, user_id: int, platform: str) -> bool:
    cred = (db.query(PlatformCredential)
              .filter_by(user_id=user_id, platform=platform).first())
    if not cred:
        return False
    db.delete(cred)
    db.commit()
    return True
