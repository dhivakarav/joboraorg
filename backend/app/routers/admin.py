"""Admin portal routes (require is_admin)."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import notifications
from ..database import get_db
from ..deps import get_admin_user
from ..models import Application, BetaInvite, Feedback, Resume, User
from ..schemas import (
    AdminUserDetails,
    AdminUserOut,
    ApplicationOut,
    PaginatedApplications,
    UserOut,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats")
def admin_stats(admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    total_users = db.query(User).filter(User.is_admin == False).count()  # noqa: E712
    pending = db.query(User).filter(User.status == "pending", User.is_admin == False).count()  # noqa: E712
    approved = db.query(User).filter(User.status == "approved", User.is_admin == False).count()  # noqa: E712
    total_apps = db.query(Application).count()
    return {
        "total_users": total_users,
        "pending_approvals": pending,
        "approved_users": approved,
        "total_applications": total_apps,
    }


@router.get("/metrics")
def admin_metrics(admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    """Beta funnel + ops metrics for the admin dashboard."""
    from datetime import timedelta

    week = datetime.utcnow() - timedelta(days=7)
    users_q = db.query(User).filter(User.is_admin == False)  # noqa: E712

    def sub(status):
        return db.query(Application).filter(Application.submission_status == status).count()

    # Funnel: how many users reached each stage.
    with_resume = db.query(Resume.user_id).distinct().count()
    with_app = db.query(Application.user_id).distinct().count()

    return {
        "users": {
            "total": users_q.count(),
            "pending": users_q.filter(User.status == "pending").count(),
            "approved": users_q.filter(User.status == "approved").count(),
            "new_this_week": users_q.filter(User.created_at >= week).count(),
        },
        "funnel": {
            "signed_up": users_q.count(),
            "uploaded_resume": with_resume,
            "tracked_a_job": with_app,
        },
        "applications": {
            "total": db.query(Application).count(),
            "tracked_or_draft": sub("Draft"),
            "manual_apply": sub("Manual Apply"),
            "submitted": sub("Submitted"),
            "verified_submitted": sub("Verified Submitted"),
            "failed": sub("Failed"),
        },
        "feedback": {
            "open": db.query(Feedback).filter(Feedback.status == "open").count(),
            "bugs_open": db.query(Feedback).filter(Feedback.status == "open",
                                                   Feedback.kind == "bug").count(),
            "total": db.query(Feedback).count(),
        },
        "invites": {
            "total": db.query(BetaInvite).count(),
            "used": db.query(BetaInvite).filter(BetaInvite.used_at.isnot(None)).count(),
        },
    }


@router.post("/invites")
def create_invites(count: int = Query(5, ge=1, le=200), note: str = Query(""),
                   admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    """Generate single-use beta invite codes."""
    import secrets
    created = []
    for _ in range(count):
        code = "JBETA-" + secrets.token_urlsafe(6).upper().replace("_", "").replace("-", "")[:8]
        inv = BetaInvite(code=code, note=note[:200])
        db.add(inv); created.append(code)
    db.commit()
    return {"created": len(created), "codes": created}


@router.get("/invites")
def list_invites(admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    rows = db.query(BetaInvite).order_by(BetaInvite.created_at.desc()).limit(200).all()
    return {"invites": [{"code": r.code, "note": r.note, "used": r.used,
                         "used_by_email": r.used_by_email,
                         "created_at": r.created_at} for r in rows]}


@router.get("/feedback")
def list_feedback(kind: Optional[str] = None, status: Optional[str] = None,
                  admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    q = db.query(Feedback)
    if kind:
        q = q.filter(Feedback.kind == kind)
    if status:
        q = q.filter(Feedback.status == status)
    rows = q.order_by(Feedback.created_at.desc()).limit(200).all()
    return {"feedback": [{"id": r.id, "kind": r.kind, "message": r.message,
                          "page": r.page, "rating": r.rating, "severity": r.severity,
                          "contact_email": r.contact_email, "status": r.status,
                          "created_at": r.created_at} for r in rows]}


@router.get("/users", response_model=list[AdminUserOut])
def list_users(admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    # H4: single grouped count query instead of N+1 per-user counts.
    counts = dict(
        db.query(Application.user_id, func.count(Application.id))
        .group_by(Application.user_id)
        .all()
    )
    users = db.query(User).filter(User.is_admin == False).order_by(User.created_at.desc()).all()  # noqa: E712
    return [
        AdminUserOut(
            id=u.id, full_name=u.full_name, email=u.email,
            status=u.status, created_at=u.created_at,
            application_count=counts.get(u.id, 0),
        )
        for u in users
    ]


@router.post("/users/{user_id}/approve")
def approve_user(user_id: int, admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    user = _get_target(db, user_id)
    user.status = "approved"
    db.commit()
    notifications.account_approved(user.email, user.full_name)
    return {"message": f"{user.full_name} approved", "status": "approved"}


@router.post("/users/{user_id}/suspend")
def suspend_user(user_id: int, admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    user = _get_target(db, user_id)
    user.status = "suspended"
    user.token_version = (user.token_version or 0) + 1  # H2: revoke active sessions immediately
    db.commit()
    return {"message": f"{user.full_name} suspended", "status": "suspended"}


@router.get("/users/{user_id}/details", response_model=AdminUserDetails)
def user_details(user_id: int, admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    user = _get_target(db, user_id)
    has_resume = db.query(Resume).filter_by(user_id=user.id).first() is not None
    total_apps = db.query(Application).filter_by(user_id=user.id).count()
    recent = (
        db.query(Application)
        .filter_by(user_id=user.id)
        .order_by(Application.applied_at.desc())
        .limit(10)
        .all()
    )
    return AdminUserDetails(
        user=UserOut.model_validate(user),
        has_resume=has_resume,
        total_applications=total_apps,
        recent_activity=[ApplicationOut.model_validate(r) for r in recent],
    )


@router.get("/applications", response_model=PaginatedApplications)
def all_applications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    portal: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    q = db.query(Application)
    if portal:
        q = q.filter(Application.portal == portal)
    if date_from:
        try:
            q = q.filter(Application.applied_at >= datetime.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            q = q.filter(Application.applied_at <= datetime.fromisoformat(date_to))
        except ValueError:
            pass
    q = q.order_by(Application.applied_at.desc())

    # `status` filters on the canonical display status (derived) — apply in Python.
    if status:
        rows = [a for a in q.all() if a.display_status == status]
        total = len(rows)
        items = rows[(page - 1) * page_size: page * page_size]
    else:
        total = q.count()
        items = q.offset((page - 1) * page_size).limit(page_size).all()
    return PaginatedApplications(items=items, total=total, page=page, page_size=page_size)


def _get_target(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id, User.is_admin == False).first()  # noqa: E712
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
