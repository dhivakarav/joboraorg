"""Job filter preferences routes."""
import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_approved_user
from ..models import JobFilter, User
from ..schemas import FiltersIn, FiltersOut

router = APIRouter(prefix="/api/filters", tags=["filters"])


@router.get("", response_model=FiltersOut)
def get_filters(user: User = Depends(get_approved_user), db: Session = Depends(get_db)):
    filt = db.query(JobFilter).filter_by(user_id=user.id).first()
    if not filt:
        return FiltersOut()
    return FiltersOut(
        roles=json.loads(filt.roles or "[]"),
        locations=json.loads(filt.locations or "[]"),
        job_types=json.loads(filt.job_types or "[]"),
        keywords=json.loads(filt.keywords or "[]"),
        min_salary=filt.min_salary,
        daily_limit=filt.daily_limit,
        min_match_score=(filt.min_match_score if filt.min_match_score is not None else 50),
    )


@router.post("", response_model=FiltersOut)
def save_filters(
    data: FiltersIn,
    user: User = Depends(get_approved_user),
    db: Session = Depends(get_db),
):
    filt = db.query(JobFilter).filter_by(user_id=user.id).first()
    if not filt:
        filt = JobFilter(user_id=user.id)
        db.add(filt)
    filt.roles = json.dumps(data.roles)
    filt.locations = json.dumps(data.locations)
    filt.job_types = json.dumps(data.job_types)
    filt.keywords = json.dumps(data.keywords)
    filt.min_salary = data.min_salary
    filt.daily_limit = data.daily_limit
    filt.min_match_score = max(0, min(100, data.min_match_score))
    db.commit()
    return data
