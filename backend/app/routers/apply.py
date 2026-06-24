"""Auto-apply control + SSE stream routes."""
import asyncio
import json

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..automation import engine
from ..database import get_db
from ..deps import get_approved_user
from ..models import Application, Resume, User
from ..queue import enqueue as enqueue_submission
from ..security import decode_access_token

router = APIRouter(prefix="/api/apply", tags=["apply"])


class ApproveIn(BaseModel):
    application_ids: list[int] = []   # specific rows; empty + all=True approves all pending
    all: bool = False


@router.post("/start")
async def start_apply(user: User = Depends(get_approved_user)):
    started = engine.start(user.id)
    if not started:
        return {"message": "Already running", "running": True}
    return {"message": "Auto-apply started", "running": True}


@router.get("/pending")
def pending_approvals(user: User = Depends(get_approved_user), db: Session = Depends(get_db)):
    """Auto-apply jobs discovered by Start Applying that are AWAITING the user's
    explicit confirmation. Nothing here has been submitted to any company."""
    rows = (db.query(Application)
            .filter_by(user_id=user.id, submission_status="Pending Approval")
            .order_by(Application.match_score.desc(), Application.applied_at.desc())
            .all())
    # HARD MATCH-SCORE FLOOR: the approval queue must never surface a job below the
    # user's current min_match_score (same threshold as Find Jobs / Matched Jobs),
    # even if it was queued under a lower threshold earlier.
    from ..models import JobFilter
    min_match = db.query(JobFilter.min_match_score).filter_by(user_id=user.id).scalar()
    min_match = min_match if min_match is not None else 50
    if min_match:
        rows = [a for a in rows if (a.match_score or 0) >= min_match]
    resume = db.query(Resume).filter_by(user_id=user.id).first()
    resume_name = (resume.file_path.split("/")[-1] if resume and resume.file_path else "")
    from ..adapters.runtime import live_ready
    ready, reason = live_ready()
    return {
        "resume_version": resume_name or "(no resume uploaded)",
        "live_ready": ready, "live_reason": reason,
        "items": [{
            "id": a.id, "job_title": a.job_title, "company": a.company,
            "location": a.location, "platform": a.platform, "apply_url": a.apply_url,
            "match_score": a.match_score, "salary_inr": a.salary_inr,
        } for a in rows],
    }


@router.post("/approve")
def approve_applications(data: ApproveIn, user: User = Depends(get_approved_user),
                         db: Session = Depends(get_db)):
    """EXPLICIT confirmation gate: only after the user approves here is a real
    submission attempted (and even then only if JOBORA_LIVE is on; otherwise the
    queue marks it Manual Apply Required — never a silent real submit)."""
    q = db.query(Application).filter_by(user_id=user.id, submission_status="Pending Approval")
    if not data.all:
        if not data.application_ids:
            return {"approved": 0, "message": "No applications selected."}
        q = q.filter(Application.id.in_(data.application_ids))
    apps = q.all()
    from ..adapters.runtime import live_ready
    ready, reason = live_ready()
    approved = 0
    for app in apps:
        app.submission_status = "Queued"
        app.submission_payload = json.dumps({"answers": {}, "external_id": app.external_application_id or "",
                                             "form_url": ""})
        db.commit()
        enqueue_submission(app.id)   # → real submit + evidence (only runs if live_ready)
        approved += 1
    return {"approved": approved, "live_ready": ready, "live_reason": reason,
            "message": (f"{approved} application(s) approved and queued for submission."
                        if ready else
                        f"{approved} approved, but live mode is OFF ({reason}) — they will be "
                        f"marked Manual Apply Required, not submitted.")}


@router.post("/stop")
async def stop_apply(user: User = Depends(get_approved_user)):
    stopped = await engine.stop(user.id)
    return {"message": "Stopped" if stopped else "Nothing running", "running": False}


@router.get("/status")
def apply_status(user: User = Depends(get_approved_user)):
    return {"running": engine.is_running(user.id)}


@router.get("/stream")
async def stream(request: Request, token: str = ""):
    """SSE stream of live apply events.

    EventSource cannot set Authorization headers, so the JWT is passed as a
    query parameter (``?token=...``).
    """
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return StreamingResponse(iter(["event: error\ndata: unauthorized\n\n"]),
                                 media_type="text/event-stream")
    user_id = int(payload["sub"])
    queue = engine.get_queue(user_id)

    async def event_gen():
        # Initial hello so the client knows the stream is open.
        yield f"data: {json.dumps({'type': 'connected'})}\n\n"
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15.0)
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") == "done":
                    # Keep stream open; client may start again. Send a keepalive.
                    pass
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"  # SSE comment to keep connection alive

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
