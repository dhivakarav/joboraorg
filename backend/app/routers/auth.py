"""Authentication routes: register, login, me, password reset."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import notifications
from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..models import PasswordReset, User
from ..ratelimit import client_ip, enforce
from ..schemas import (
    ForgotPasswordIn,
    LoginIn,
    RefreshIn,
    RegisterIn,
    RegisterOut,
    ResendVerificationIn,
    ResetPasswordIn,
    TokenOut,
    UserOut,
    VerifyEmailIn,
)
from ..security import (
    decode_access_token,
    generate_reset_token,
    hash_password,
    hash_token,
    issue_tokens,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _validate_password(pw: str) -> None:
    """H5 signup password policy: >=8 chars, with letters and digits."""
    if len(pw) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if not any(c.isalpha() for c in pw) or not any(c.isdigit() for c in pw):
        raise HTTPException(status_code=400, detail="Password must include both letters and numbers")


@router.post("/register", response_model=RegisterOut)
def register(data: RegisterIn, request: Request, db: Session = Depends(get_db)):
    enforce("register", client_ip(request), settings.RL_REGISTER_PER_HOUR, 3600)
    _validate_password(data.password)
    email = data.email.strip().lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Closed-beta gate: consume a single-use invite code when enabled.
    invite = None
    if settings.BETA_INVITE_REQUIRED:
        from ..models import BetaInvite
        code = (data.invite_code or "").strip()
        invite = db.query(BetaInvite).filter_by(code=code).first() if code else None
        if not invite or invite.used:
            raise HTTPException(status_code=403, detail="A valid beta invite code is required")
    user = User(
        full_name=data.full_name,
        email=email,
        hashed_password=hash_password(data.password),
        phone=data.phone,
        years_experience=data.years_experience,
        job_title=data.job_title,
        status="pending",
        is_admin=False,
        email_verified=False,
    )
    # H5: issue an email-verification token (hashed at rest; raw emailed).
    raw_verify = generate_reset_token()
    user.email_verify_hash = hash_token(raw_verify)
    user.email_verify_expires = datetime.utcnow() + timedelta(hours=24)
    db.add(user)
    db.commit()
    db.refresh(user)
    if invite is not None:
        invite.used_by_email = email
        invite.used_at = datetime.utcnow()
        db.commit()
    notifications.account_pending(user.email, user.full_name)
    # Signup is NOT rolled back if the verification email fails (resilience): the
    # account is created, the failure is loudly logged by _send, and we hand the
    # user a clear hint to use "Resend verification" so they're never left guessing.
    sent = _send_verification(user, raw_verify)
    user.notice = None if sent else (
        "Account created, but we couldn't send your verification email right now. "
        "Use 'Resend verification' on the sign-in screen to get a new link.")

    from .. import analytics
    analytics.capture(analytics.SIGNUP, user.id,
                      {"seeker_type": user.seeker_type or "", "invited": invite is not None})
    return user


def _send_verification(user: User, raw_token: str) -> bool:
    """Send the verification email. Returns True on success, False on failure
    (failure is already logged at ERROR by notifications._send)."""
    link = f"/verify-email?token={raw_token}"
    return notifications._send(
        user.email, "Verify your Jobara email",
        f"Hi {user.full_name},\n\nConfirm your email to activate your account:\n"
        f"{settings.APP_BASE_URL}{link}\n\n(Link valid 24h.)",
    )


@router.post("/verify-email")
def verify_email(data: VerifyEmailIn, db: Session = Depends(get_db)):
    h = hash_token(data.token)
    user = db.query(User).filter(User.email_verify_hash == h).first()
    if not user or not user.email_verify_expires or user.email_verify_expires < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Verification link is invalid or expired")
    user.email_verified = True
    user.email_verify_hash = ""
    user.email_verify_expires = None
    db.commit()
    return {"message": "Email verified. You can sign in once an admin approves your account."}


@router.post("/resend-verification")
def resend_verification(data: ResendVerificationIn, request: Request, db: Session = Depends(get_db)):
    """Re-send the verification email. Generic response either way so the endpoint
    can't be used to probe which emails are registered."""
    enforce("resend_verification", client_ip(request), settings.RL_REGISTER_PER_HOUR, 3600)
    generic = {"message": "If that email is registered and unverified, a new verification link has been sent."}
    email = data.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if user and not user.email_verified:
        raw_verify = generate_reset_token()
        user.email_verify_hash = hash_token(raw_verify)
        user.email_verify_expires = datetime.utcnow() + timedelta(hours=24)
        db.commit()
        _send_verification(user, raw_verify)
    return generic


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, request: Request, db: Session = Depends(get_db)):
    enforce("login", client_ip(request), settings.RL_LOGIN_PER_MIN, 60)
    email = data.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    # Use the same message and status for "email not found" and "wrong password"
    # so attackers cannot enumerate registered emails via differing responses.
    _BAD_CREDS = HTTPException(status_code=401, detail="Email or password is incorrect")
    if not user:
        raise _BAD_CREDS
    if not verify_password(data.password, user.hashed_password):
        raise _BAD_CREDS

    if not user.is_admin and user.status == "pending":
        raise HTTPException(status_code=403, detail="Your account is pending admin approval")
    if not user.is_admin and user.status == "suspended":
        raise HTTPException(status_code=403, detail="Your account has been suspended")
    # Email-verification gate (ON by default). Block unverified non-admins with a
    # distinct message the frontend detects to offer a "resend verification" action.
    if settings.REQUIRE_EMAIL_VERIFICATION and not user.is_admin and not user.email_verified:
        raise HTTPException(status_code=403,
                            detail="Please verify your email before logging in.")

    tokens = issue_tokens(user)
    from .. import analytics
    analytics.capture(analytics.LOGIN, user.id, {"is_admin": user.is_admin})
    return TokenOut(**tokens, is_admin=user.is_admin, status=user.status,
                    must_change_password=bool(user.must_change_password),
                    email_verified=bool(user.email_verified))


@router.post("/refresh", response_model=TokenOut)
def refresh(data: RefreshIn, db: Session = Depends(get_db)):
    """H2: exchange a valid refresh token for a new access+refresh pair."""
    payload = decode_access_token(data.refresh_token)
    if not payload or payload.get("type") != "refresh" or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user or int(payload.get("tv", 0)) != int(user.token_version or 0):
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")
    if user.status == "suspended":
        raise HTTPException(status_code=403, detail="Account suspended")
    tokens = issue_tokens(user)
    return TokenOut(**tokens, is_admin=user.is_admin, status=user.status,
                    must_change_password=bool(user.must_change_password),
                    email_verified=bool(user.email_verified))


@router.post("/logout")
def logout(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """H2: revoke ALL of this user's tokens (logout everywhere) by bumping version."""
    user.token_version = (user.token_version or 0) + 1
    db.commit()
    return {"message": "Logged out — all sessions revoked"}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordIn, db: Session = Depends(get_db)):
    """Begin a password reset.

    Always returns the same generic message so attackers can't enumerate which
    emails are registered. When EXPOSE_RESET_TOKEN is on (no SMTP in dev), the
    usable reset link is included in the response.
    """
    generic = {"message": "If an account exists for that email, a reset link has been generated."}
    user = db.query(User).filter(User.email == data.email.strip().lower()).first()
    if not user:
        return generic

    # Invalidate any prior outstanding tokens for this user.
    db.query(PasswordReset).filter(
        PasswordReset.user_id == user.id, PasswordReset.used == False  # noqa: E712
    ).update({"used": True})

    raw_token = generate_reset_token()
    pr = PasswordReset(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        expires_at=datetime.utcnow() + timedelta(minutes=settings.RESET_TOKEN_TTL_MINUTES),
    )
    db.add(pr)
    db.commit()

    reset_link = f"/reset-password?token={raw_token}"
    notifications.password_reset(user.email, user.full_name, reset_link)

    if settings.EXPOSE_RESET_TOKEN:
        return {
            **generic,
            "reset_token": raw_token,
            "reset_link": reset_link,
            "expires_in_minutes": settings.RESET_TOKEN_TTL_MINUTES,
            "dev_note": "Email isn't configured, so the link is returned here for development.",
        }
    return generic


@router.post("/reset-password")
def reset_password(data: ResetPasswordIn, db: Session = Depends(get_db)):
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")

    pr = (
        db.query(PasswordReset)
        .filter(PasswordReset.token_hash == hash_token(data.token), PasswordReset.used == False)  # noqa: E712
        .first()
    )
    if not pr or pr.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired")

    user = db.query(User).filter(User.id == pr.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="Account no longer exists")

    user.hashed_password = hash_password(data.new_password)
    pr.used = True
    db.commit()
    return {"message": "Password updated. You can now sign in with your new password."}
