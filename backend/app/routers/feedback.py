"""Beta feedback + bug-report routes.

A signed-in user can submit feedback or a bug report from anywhere in the app.
Stored in the `feedback` table; admins triage via the admin routes. Lightweight
and fully self-contained — no external dependency.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import analytics
from ..database import get_db
from ..deps import get_approved_user
from ..models import Feedback, User

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


class FeedbackIn(BaseModel):
    kind: str = "feedback"          # feedback | bug
    message: str
    page: str = ""
    rating: Optional[int] = None    # 1-5 (feedback)
    severity: str = ""              # low | medium | high (bug)
    contact_email: str = ""


@router.post("")
def submit_feedback(data: FeedbackIn, user: User = Depends(get_approved_user),
                    db: Session = Depends(get_db)):
    msg = (data.message or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Message is required")
    kind = "bug" if data.kind == "bug" else "feedback"
    fb = Feedback(
        user_id=user.id, kind=kind, message=msg[:4000], page=data.page[:200],
        rating=data.rating if (data.rating and 1 <= data.rating <= 5) else None,
        severity=data.severity if data.severity in ("low", "medium", "high") else "",
        contact_email=(data.contact_email or user.email)[:200], status="open",
    )
    db.add(fb); db.commit(); db.refresh(fb)
    analytics.capture(analytics.FEEDBACK_SUBMITTED, user.id,
                      {"kind": kind, "page": data.page, "rating": fb.rating})
    return {"id": fb.id, "message": "Thanks — your "
            + ("bug report" if kind == "bug" else "feedback") + " was received."}
