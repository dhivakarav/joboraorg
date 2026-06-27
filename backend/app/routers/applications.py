"""Application history routes (paginated) + lifecycle + submission evidence."""
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_approved_user
from ..models import Application, JobFilter, User
from ..schemas import ApplicationOut, EvidenceOut, PaginatedApplications, StatusUpdateIn
from ..status import USER_SETTABLE_STAGES as USER_SETTABLE

router = APIRouter(prefix="/api/applications", tags=["applications"])

# The match-score floor only governs DISCOVERY output — the rows Start Applying
# auto-generates: Matched Jobs ("Manual Apply") and the approval queue ("Pending
# Approval"). User-curated rows (Tracked/Saved) and in-funnel rows (Interview/
# Offer/Submitted/…) are never hidden by the slider — you can't lose a job you
# saved or are interviewing for just because you raised the threshold.
_FLOOR_APPLIES_TO = {"Manual Apply", "Pending Approval"}

# USER_SETTABLE (imported above from status.py, single source of truth): the
# stages a user may self-assign — automation never sets these, so an automated
# "Applied"-style claim can't be fabricated.


@router.get("", response_model=PaginatedApplications)
def list_applications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    portal: Optional[str] = None,
    mode: Optional[str] = Query(None, description="filter by application_mode: auto_applied | manual_link_provided"),
    sort: Optional[str] = Query(None, description="match_score to sort by match desc (default: recent first)"),
    user: User = Depends(get_approved_user),
    db: Session = Depends(get_db),
):
    q = db.query(Application).filter(Application.user_id == user.id)
    if portal:
        q = q.filter(Application.portal == portal)
    if mode:
        q = q.filter(Application.application_mode == mode)

    # DB-level prefilter on submission_status to narrow the Python pass when a
    # display_status filter is requested. display_status is a Python property
    # (not a DB column), so an exact DB filter isn't possible, but each canonical
    # status maps to a small set of submission_status values we CAN push to the DB.
    # This turns the worst-case from "load all N rows" to "load only the matching
    # submission_status bucket", which is typically orders of magnitude smaller.
    _SS_PREFILTER: dict = {
        "Draft":               ["Draft", ""],
        "Tracked":             ["Draft"],
        "Manual Apply":        ["Manual Apply", "Manual Apply Required"],
        "Pending Approval":    ["Pending Approval"],
        "Queued":              ["Queued", "Processing"],
        "Submitted":           ["Submitted", "Verified Submitted"],
        "Verified Submitted":  ["Verified Submitted", "Submitted"],
        "Submitted (Unverified)": ["Submitted", "Verified Submitted"],
        "Failed":              ["Failed", "CAPTCHA Required"],
        "Failed — No Confirmation":  ["Failed — No Confirmation"],
        "Failed — Form Not Found":   ["Failed — Form Not Found"],
        "Failed — Submit Not Found": ["Failed — Submit Not Found"],
        # User-set stages live in the legacy `status` column — no prefilter possible.
        "Interview": None, "Offer": None, "Rejected": None,
    }
    if status and status in _SS_PREFILTER:
        pre = _SS_PREFILTER[status]
        if pre is not None:
            q = q.filter(Application.submission_status.in_(pre))

    if sort == "match_score":
        q = q.order_by(Application.match_score.desc(), Application.applied_at.desc())
    else:
        q = q.order_by(Application.applied_at.desc())

    min_match = db.query(JobFilter.min_match_score).filter_by(user_id=user.id).scalar()
    min_match = min_match if min_match is not None else 50

    def _passes_floor(a) -> bool:
        if not min_match:
            return True
        if a.display_status not in _FLOOR_APPLIES_TO:
            return True
        return (a.match_score or 0) >= min_match

    # Python-side pass for exact display_status and match-floor (both are derived).
    # The DB prefilter above has already reduced the result set significantly.
    rows = [a for a in q.all() if _passes_floor(a) and (not status or a.display_status == status)]
    total = len(rows)
    items = rows[(page - 1) * page_size: page * page_size]
    return PaginatedApplications(items=items, total=total, page=page, page_size=page_size)


@router.patch("/{app_id}/status", response_model=ApplicationOut)
def update_status(
    app_id: int,
    data: StatusUpdateIn,
    user: User = Depends(get_approved_user),
    db: Session = Depends(get_db),
):
    if data.status not in USER_SETTABLE:
        raise HTTPException(
            status_code=400,
            detail=("Invalid status. Submission outcomes are evidence-derived and "
                    "cannot be set manually; allowed: " + ", ".join(sorted(USER_SETTABLE))))
    app = db.query(Application).filter_by(id=app_id, user_id=user.id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    app.status = data.status
    db.commit()
    db.refresh(app)
    return app


@router.delete("/{app_id}", status_code=204)
def delete_application(
    app_id: int,
    user: User = Depends(get_approved_user),
    db: Session = Depends(get_db),
):
    """Remove a tracked application from the user's Activity Log.

    Only Draft/Tracked/Saved/Skipped rows may be deleted — applications that
    are Queued, Processing, Submitted, or Verified Submitted cannot be deleted
    because they represent real in-flight or completed submissions.
    """
    app = db.query(Application).filter_by(id=app_id, user_id=user.id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    if app.display_status in ("Queued", "Processing", "Submitted",
                              "Verified Submitted", "Submitted (Unverified)"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete an application with status '{app.display_status}'. "
                   "Only Draft, Tracked, Saved, Skipped, Manual Apply, and Failed "
                   "entries can be removed.")
    db.delete(app)
    db.commit()


def _owned_app(db: Session, user: User, app_id: int) -> Application:
    app = db.query(Application).filter_by(id=app_id, user_id=user.id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app


def _evidence_dict(app: Application) -> dict:
    try:
        return json.loads(app.submission_evidence or "{}")
    except (ValueError, TypeError):
        return {}


def _screenshot_ref(ev: dict):
    """Return (storage_key_or_None, local_path_or_None) for the screenshot."""
    return ev.get("screenshot_key"), ev.get("screenshot")


@router.get("/{app_id}/evidence", response_model=EvidenceOut)
def get_evidence(app_id: int, user: User = Depends(get_approved_user),
                 db: Session = Depends(get_db)):
    """Submission evidence metadata + a SHORT-LIVED screenshot URL (owner only)."""
    from ..security import create_evidence_token
    from ..storage import storage

    app = _owned_app(db, user, app_id)
    ev = _evidence_dict(app)
    key, local = _screenshot_ref(ev)
    has_shot = bool((key and storage.exists(key)) or (local and Path(local).exists()))

    url = ""
    if has_shot:
        presigned = storage.url(key) if key else None
        if presigned:
            url = presigned  # S3 presigned (already short-lived)
        else:
            tok = create_evidence_token(app.id)
            url = f"/api/applications/{app.id}/evidence/screenshot?token={tok}"

    return EvidenceOut(
        application_id=app.id,
        display_status=app.display_status,
        submission_status=app.submission_status,
        reference_id=app.application_id or app.external_application_id or "",
        external_application_id=app.external_application_id or "",
        confirmation_url=app.confirmation_url or "",
        evidence_available=bool(app.evidence_available),
        submitted_at=app.submitted_at,
        has_screenshot=has_shot,
        screenshot_url=url,
        platform_response=ev.get("platform_response", ""),
        failure_reason=ev.get("failure_reason", ""),
    )


@router.get("/{app_id}/evidence/screenshot")
def get_evidence_screenshot(app_id: int, token: str = "", db: Session = Depends(get_db)):
    """Serve the confirmation screenshot via a SHORT-LIVED, evidence-scoped token.

    The token (?token=) is purpose-scoped to this app's evidence and expires
    quickly (EVIDENCE_URL_TTL) — it is NOT a reusable access token in a URL.
    """
    from ..security import verify_evidence_token
    from ..storage import storage

    if not verify_evidence_token(token, app_id):
        raise HTTPException(status_code=401, detail="Invalid or expired evidence link")
    app = db.query(Application).filter_by(id=app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    ev = _evidence_dict(app)
    key, local = _screenshot_ref(ev)
    data = storage.open_bytes(key) if key else None
    if data is not None:
        from fastapi.responses import Response
        return Response(content=data, media_type="image/png")
    if local and Path(local).exists():
        return FileResponse(local, media_type="image/png",
                            filename=f"application_{app.id}_confirmation.png")
    raise HTTPException(status_code=404, detail="No screenshot evidence for this application")
