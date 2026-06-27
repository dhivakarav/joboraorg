"""User dashboard stats route."""
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_approved_user
from ..models import Application, User
from ..schemas import ApplicationOut
from ..services import load_profile

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats")
def dashboard_stats(user: User = Depends(get_approved_user), db: Session = Depends(get_db)):
    from ..status import CANONICAL, DRAFT, FAILED, MANUAL, SUBMITTED, TRACKED, VERIFIED
    from ..jobs.eligibility import (eligibility, has_internship_signal,
                                    internships_only_default)

    # Count total in DB rather than loading all rows.
    total = db.query(func.count(Application.id)).filter(
        Application.user_id == user.id).scalar() or 0

    # submission_status grouping is cheaply done in DB; display_status is a Python
    # property so we still need a limited in-Python pass, but we cap it at 500
    # rows instead of loading everything. This is an acceptable trade-off for the
    # counts panel until display_status becomes a persisted column (Phase 3).
    sample = (db.query(Application)
               .filter(Application.user_id == user.id)
               .order_by(Application.applied_at.desc())
               .limit(500)
               .all())
    counts = {s: 0 for s in CANONICAL}
    for a in sample:
        counts[a.display_status] = counts.get(a.display_status, 0) + 1

    # Dashboard only needs text profile fields for eligibility scoring — no PDF needed.
    profile = load_profile(db, user, materialize=False)
    io = internships_only_default(profile)
    recent_all = (
        db.query(Application)
        .filter(Application.user_id == user.id)
        .order_by(Application.applied_at.desc())
        .limit(60)
        .all()
    )

    def _show(r):
        job = {"title": r.job_title, "description_snippet": ""}
        if not eligibility(job, profile)["eligible"]:
            return False
        if io and not has_internship_signal(job):
            return False
        return True

    recent = [r for r in recent_all if _show(r)][:8]
    return {
        "total": total,
        "verified_submitted": counts[VERIFIED],
        "submitted": counts[SUBMITTED],
        "tracked": counts[TRACKED],
        "manual_apply": counts[MANUAL],
        "draft": counts[DRAFT],
        "failed": counts[FAILED],
        "by_status": counts,
        "recent_activity": [ApplicationOut.model_validate(r).model_dump(mode="json") for r in recent],
    }
