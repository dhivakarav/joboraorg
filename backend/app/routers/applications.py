"""Application history routes (paginated) + lifecycle + submission evidence."""
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_approved_user
from ..models import Application, User
from ..schemas import ApplicationOut, EvidenceOut, PaginatedApplications, StatusUpdateIn

router = APIRouter(prefix="/api/applications", tags=["applications"])

# A user may only move a row between honest, non-submission lifecycle states.
# Submission outcomes (Submitted / Verified Submitted / Failed) are system-derived
# from real evidence and can NEVER be set by hand — and "Applied" is retired.
USER_SETTABLE = {"Saved", "Tracked", "Skipped"}


@router.get("", response_model=PaginatedApplications)
def list_applications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    portal: Optional[str] = None,
    user: User = Depends(get_approved_user),
    db: Session = Depends(get_db),
):
    q = db.query(Application).filter(Application.user_id == user.id)
    if portal:
        q = q.filter(Application.portal == portal)
    q = q.order_by(Application.applied_at.desc())

    # `status` filters on the canonical display status (derived), so apply it in
    # Python — it never matches the raw stored `status` column anymore.
    if status:
        rows = [a for a in q.all() if a.display_status == status]
        total = len(rows)
        items = rows[(page - 1) * page_size: page * page_size]
    else:
        total = q.count()
        items = q.offset((page - 1) * page_size).limit(page_size).all()
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
