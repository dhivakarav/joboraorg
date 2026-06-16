"""User dashboard stats route."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_approved_user
from ..models import Application, User
from ..schemas import ApplicationOut

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats")
def dashboard_stats(user: User = Depends(get_approved_user), db: Session = Depends(get_db)):
    from ..status import CANONICAL, DRAFT, FAILED, MANUAL, SUBMITTED, TRACKED, VERIFIED

    apps = db.query(Application).filter(Application.user_id == user.id).all()
    total = len(apps)

    # Count by the canonical, evidence-gated display status — never by "Applied".
    counts = {s: 0 for s in CANONICAL}
    for a in apps:
        counts[a.display_status] = counts.get(a.display_status, 0) + 1

    # Recent activity mirrors discovery filtering: hides "Not Recommended" roles,
    # and (for students/freshers) keeps only internship/new-grad-signal roles.
    from ..jobs.eligibility import (eligibility, has_internship_signal,
                                    internships_only_default)
    from ..services import load_profile
    profile = load_profile(db, user)
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
        # The only metric that means a confirmed, evidenced submission:
        "verified_submitted": counts[VERIFIED],
        "submitted": counts[SUBMITTED],
        "tracked": counts[TRACKED],
        "manual_apply": counts[MANUAL],
        "draft": counts[DRAFT],
        "failed": counts[FAILED],
        "by_status": counts,
        "recent_activity": [ApplicationOut.model_validate(r).model_dump(mode="json") for r in recent],
    }
