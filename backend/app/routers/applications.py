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
    if sort == "match_score":
        q = q.order_by(Application.match_score.desc(), Application.applied_at.desc())
    else:
        q = q.order_by(Application.applied_at.desc())

    # HARD MATCH-SCORE FLOOR (same threshold as Find Jobs): Matched Jobs and the
    # Pending Approval queue must never show a row below the user's min_match_score.
    # Rows the user has actively advanced into their human funnel are exempt so a
    # raised slider never hides a job they're already interviewing for.
    min_match = db.query(JobFilter.min_match_score).filter_by(user_id=user.id).scalar()
    min_match = min_match if min_match is not None else 50

    def _passes_floor(a) -> bool:
        if not min_match:
            return True
        if a.display_status not in _FLOOR_APPLIES_TO:
            return True          # user-curated / in-funnel rows are never floored
        return (a.match_score or 0) >= min_match

    # `status` filters on the canonical display status (derived), so apply it in
    # Python — it never matches the raw stored `status` column anymore. The match
    # floor is also applied in Python so it composes with the derived-status filter.
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
