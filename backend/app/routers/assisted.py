"""Assisted Apply — Lever, Ashby & Internshala (captcha-/login-gated platforms).

Lever/Ashby ship hCaptcha/reCAPTCHA on every public form and Internshala is
account-gated (login required, no public submit API), so unattended submission is
impossible / not permitted. Assisted Apply is the honest flow:

  1. /assisted/prepare  → Jobora prefills the form from the user's REAL profile,
     surfaces the required screening questions for the user to review/answer, and
     returns the genuine apply URL. Records the job as "Manual Apply" (assisted).
     NOTHING is submitted; the user completes captcha + submit on the real page.
  2. /assisted/record   → the user reports the outcome with PROOF (confirmation
     URL + reference id + a confirmation screenshot). Only with all three does the
     row become "Verified Submitted"; otherwise "Submitted". Never "Applied"
     without proof.

No fabricated data: prefill comes only from the user's profile; evidence comes
only from what the user actually captured on the real confirmation page.
"""
from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..adapters import adapter_for
from ..database import get_db
from ..deps import get_approved_user
from ..models import Application, User
from ..services import load_profile
from ..storage import storage

router = APIRouter(prefix="/api/jobs/assisted", tags=["assisted-apply"])

# Required screening questions are platform-/posting-specific and detected live by
# the G1 inspectors; for the prepare step we describe what the user should expect.
_PLATFORM_NOTE = {
    "Lever": "Lever forms include an hCaptcha you must complete before submitting.",
    "Ashby": "Ashby forms include a reCAPTCHA and submit in-app (no page redirect).",
    "Internshala": ("Internshala requires you to be signed in. Open the listing, "
                    "sign in if prompted, then complete and submit the application."),
}

# Captcha each platform ships on its public form (empty = none; e.g. login-gated).
_PLATFORM_CAPTCHA = {"Lever": "hCaptcha", "Ashby": "reCAPTCHA"}

# Platforms eligible for the Assisted Apply (prefill + finish-on-portal) flow.
_ASSISTED_PLATFORMS = ("Lever", "Ashby", "Internshala")


def _prefill_from_profile(profile: dict) -> dict:
    """Build a prefill packet from the user's REAL profile only — no fabrication.

    Keys map to what `load_profile` actually returns (name/linkedin_url/etc.).
    """
    return {
        "full_name": profile.get("name", ""),
        "email": profile.get("email", ""),
        "phone": profile.get("phone", ""),
        "linkedin": profile.get("linkedin_url", ""),
        "portfolio": profile.get("portfolio_url", ""),
        "location": profile.get("location", "") or (profile.get("locations") or [""])[0],
        "resume_filename": (profile.get("resume_path", "") or "").split("/")[-1],
        "has_resume": bool(profile.get("resume_path")),
    }


@router.post("/prepare")
def prepare_assisted(payload: dict, user: User = Depends(get_approved_user),
                     db: Session = Depends(get_db)):
    """Prefill + review packet for an assisted (captcha-gated) apply. No submit."""
    job = payload.get("job") or {}
    if not job.get("apply_url"):
        raise HTTPException(status_code=400, detail="job.apply_url required")
    adapter = adapter_for(job)
    if adapter.platform not in _ASSISTED_PLATFORMS:
        raise HTTPException(status_code=400,
                            detail=f"Assisted Apply supports {'/'.join(_ASSISTED_PLATFORMS)}; "
                                   f"got {adapter.platform}")

    # prepare only needs text fields (name/email/phone) and the resume filename —
    # not the actual PDF. materialize=False avoids creating a temp file here.
    profile = load_profile(db, user, materialize=False)

    # Check resume exists via DB rather than a materialized path.
    from ..models import Resume as _Resume
    resume_rec = db.query(_Resume).filter_by(user_id=user.id).first()
    if not resume_rec:
        raise HTTPException(status_code=400, detail="Upload a resume before applying")
    resume_filename = (resume_rec.file_path or "").split("/")[-1]

    fp = job.get("fingerprint") or job.get("apply_url")
    app = db.query(Application).filter_by(user_id=user.id, job_url_hash=fp).first()
    if not app:
        app = Application(
            user_id=user.id, portal=job.get("source", adapter.platform),
            source=job.get("source", ""), platform=adapter.platform,
            job_title=job.get("title", ""), company=job.get("company", ""),
            location=job.get("location", ""), salary=job.get("salary", ""),
            salary_inr=job.get("salary_inr", ""), apply_url=job["apply_url"],
            verified=job.get("verified", False), manual_required=True,
            job_url_hash=fp, status="Tracked", submission_status="Manual Apply",
        )
        db.add(app); db.commit(); db.refresh(app)

    from .. import analytics
    analytics.capture(analytics.APPLICATION_STARTED, user.id,
                      {"platform": adapter.platform, "mode": "assisted"})
    analytics.capture(analytics.MANUAL_APPLY, user.id,
                      {"platform": adapter.platform, "mode": "assisted"})

    prefill = {
        "full_name": profile.get("name", ""),
        "email": profile.get("email", ""),
        "phone": profile.get("phone", ""),
        "linkedin": profile.get("linkedin_url", ""),
        "portfolio": profile.get("portfolio_url", ""),
        "location": profile.get("location", "") or (profile.get("locations") or [""])[0],
        "resume_filename": resume_filename,
        "has_resume": True,
    }
    captcha = _PLATFORM_CAPTCHA.get(adapter.platform, "")
    required_fields = [
        {"label": "Full name", "value": prefill["full_name"], "required": True},
        {"label": "Email", "value": prefill["email"], "required": True},
        {"label": "Phone", "value": prefill["phone"], "required": True},
        {"label": "Resume", "value": prefill["resume_filename"], "required": True},
        {"label": "LinkedIn", "value": prefill["linkedin"], "required": False},
        {"label": "Portfolio", "value": prefill["portfolio"], "required": False},
    ]
    return {
        "application_id": app.id,
        "platform": adapter.platform,
        "apply_url": job["apply_url"],
        "prefill": prefill,
        "required_fields": required_fields,
        "resume_filename": resume_filename,
        "captcha": captcha,
        "captcha_note": _PLATFORM_NOTE.get(adapter.platform, ""),
        "screening_note": (
            f"This {adapter.platform} posting may include screening questions "
            "(e.g. work authorization, \"why this role\"). Answer them truthfully on "
            "the portal — Jobora never auto-fills answers under your name."),
        "instructions": [
            "Review the details Jobora prepared from your profile.",
            (f"Open the apply page — fill any screening questions, complete the {captcha}, and submit."
             if captcha else
             "Open the listing — sign in if prompted, fill any screening questions, and submit."),
            "Come back and record your confirmation (URL + reference id + screenshot).",
        ],
        "status": app.display_status,
    }


@router.post("/record")
async def record_evidence(
    application_id: int = Form(...),
    confirmation_url: str = Form(""),
    reference_id: str = Form(""),
    screenshot: UploadFile = File(None),
    user: User = Depends(get_approved_user),
    db: Session = Depends(get_db),
):
    """Record a REAL outcome with proof. Verified Submitted only if all three exist."""
    app = db.query(Application).filter_by(id=application_id, user_id=user.id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    ev = {}
    try:
        ev = json.loads(app.submission_evidence or "{}")
    except (ValueError, TypeError):
        ev = {}

    screenshot_stored = False
    if screenshot is not None:
        data = await screenshot.read()
        if data:
            key = f"evidence/{app.id}/user_confirmation_{datetime.utcnow().timestamp():.0f}.png"
            storage.save_bytes(key, data)
            ev["screenshot_key"] = key
            ev["source"] = "user-captured (assisted apply)"
            screenshot_stored = True

    app.confirmation_url = confirmation_url or app.confirmation_url
    app.application_id = reference_id or app.application_id
    app.external_application_id = app.application_id
    app.evidence_available = screenshot_stored or bool(ev.get("screenshot") or ev.get("screenshot_key"))
    app.submission_evidence = json.dumps(ev)

    # INTEGRITY GATE: Verified Submitted requires id + confirmation_url + evidence.
    if app.application_id and app.confirmation_url and app.evidence_available:
        app.submission_status = "Verified Submitted"
        app.status = "Submitted"
        app.submitted_at = datetime.utcnow()
    elif app.confirmation_url or screenshot_stored:
        app.submission_status = "Submitted"     # attempted with partial proof
        app.submitted_at = datetime.utcnow()
    # else: stays Manual Apply — nothing claimed without proof.
    db.commit(); db.refresh(app)

    from .. import analytics
    if app.submission_status in ("Submitted", "Verified Submitted"):
        analytics.capture(analytics.APPLICATION_SUBMITTED, user.id,
                          {"platform": app.platform, "mode": "assisted"})
    if app.display_status == "Verified Submitted":
        analytics.capture(analytics.VERIFIED_SUBMITTED, user.id,
                          {"platform": app.platform})

    return {
        "application_id": app.id,
        "submission_status": app.submission_status,
        "display_status": app.display_status,
        "verified": app.display_status == "Verified Submitted",
        "missing": [m for m, ok in (
            ("reference_id", bool(app.application_id)),
            ("confirmation_url", bool(app.confirmation_url)),
            ("screenshot", bool(app.evidence_available))) if not ok],
    }
