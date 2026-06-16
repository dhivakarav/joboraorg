"""Profile and password update routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_approved_user, get_current_user
from ..models import User
from ..schemas import PasswordChangeIn, ProfileUpdateIn, UserOut
from ..security import hash_password, verify_password

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.put("/update", response_model=UserOut)
def update_profile(
    data: ProfileUpdateIn,
    user: User = Depends(get_approved_user),
    db: Session = Depends(get_db),
):
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.phone is not None:
        user.phone = data.phone
    if data.years_experience is not None:
        user.years_experience = data.years_experience
    if data.job_title is not None:
        user.job_title = data.job_title
    if data.seeker_type is not None and data.seeker_type in ("student", "fresher", "experienced", ""):
        user.seeker_type = data.seeker_type
    db.commit()
    db.refresh(user)
    return user


@router.put("/password")
def change_password(
    data: PasswordChangeIn,
    user: User = Depends(get_current_user),   # any authenticated user, incl. admin
    db: Session = Depends(get_db),
):
    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
    user.hashed_password = hash_password(data.new_password)
    user.must_change_password = False   # clears the forced-change flag
    user.token_version = (user.token_version or 0) + 1  # H2: revoke existing sessions
    db.commit()
    return {"message": "Password updated"}
