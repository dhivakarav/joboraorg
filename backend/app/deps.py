"""Shared FastAPI dependencies for auth/authorization."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import User
from .security import decode_access_token

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_access_token(creds.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    # Refresh tokens must not be usable as access tokens.
    if payload.get("type") == "refresh":
        raise HTTPException(status_code=401, detail="Refresh token cannot be used for access")
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    # H2 revocation: token_version must match. Bumping it on the user invalidates
    # every previously-issued token (logout-all, password change, suspend).
    if int(payload.get("tv", 0)) != int(user.token_version or 0):
        raise HTTPException(status_code=401, detail="Token has been revoked — please sign in again")
    return user


def get_approved_user(user: User = Depends(get_current_user)) -> User:
    if user.is_admin:
        raise HTTPException(status_code=403, detail="Admin cannot access user features")
    if user.status == "pending":
        raise HTTPException(status_code=403, detail="Account pending admin approval")
    if user.status == "suspended":
        raise HTTPException(status_code=403, detail="Account suspended")
    return user


def get_admin_user(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
