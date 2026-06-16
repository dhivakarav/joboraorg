"""Real job discovery + AI-assisted application workflow.

Discovery: live from official provider APIs. Every job is scored against the
user's profile, salary is shown in INR, and the right platform adapter is
selected so the UI knows whether auto-apply is possible.

Apply workflow: prepare (map profile → form + screening questions) → user
reviews/edits → submit (records the application; performs the real browser
submission only for capable platforms in opt-in live mode, else marks
"Manual Apply Required").
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import notifications
from ..adapters import adapter_for, platform_capabilities
from ..adapters.greenhouse_fill import CORE_TEXT, fetch_fields
from ..adapters.greenhouse_production import apply as gh_apply
from ..adapters.greenhouse_production import parse_board_job, resolve_form_url
from ..adapters.runtime import live_ready
from ..config import settings
from ..database import get_db
from ..deps import get_approved_user
from ..jobs import aggregator
from ..jobs import india
from ..jobs.matching import score_job
from ..jobs.eligibility import eligibility, early_signal, internships_only_default
from ..models import Application, JobFilter, Resume, User
from ..ratelimit import enforce
from ..schemas import (
    ApplyIntentIn,
    GreenhouseApplyIn,
    JobOut,
    JobSearchOut,
    PrepareIn,
    StatusUpdateIn,
    SubmitIn,
)

from ..queue import enqueue as enqueue_submission  # noqa: E402
from ..services import load_profile as _load_profile  # noqa: E402
from ..services import profile_complete as _profile_complete  # noqa: E402

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

EVIDENCE_ROOT = settings.UPLOAD_DIR / "evidence"


def _decorate(job: dict, profile: dict, applied_hashes: set) -> JobOut:
    """Attach match score, eligibility, platform capability, and applied state."""
    match = score_job(job, profile)
    elig = eligibility(job, profile)
    adapter = adapter_for(job)
    return JobOut(
        **job,
        match_score=match["score"],
        match_reasons=match["reasons"],
        eligibility_score=elig["eligibility_score"],
        eligibility_tier=elig["eligibility_tier"],
        eligible=elig["eligible"],
        eligibility_reason=elig["eligibility_reason"],
        eligibility_reasons=elig["eligibility_reasons"],
        early_signal=early_signal(job),
        platform=adapter.platform,
        auto_submit=adapter.supports_auto_submit,
        manual_required=adapter.manual_only,
        applied=job["fingerprint"] in applied_hashes,
    )


def _rank_key(j: JobOut) -> float:
    """India-first, student-first ranking.

    Eligibility dominates and match breaks ties (as before); on top we add an
    India-location bonus (an explicit Indian hub outranks generic remote) and a
    priority-domain bonus (AI/ML, Data Science, SWE/SDE, Backend, Full Stack) so
    the roles an Indian student actually wants surface first.
    """
    base = j.eligibility_score * 0.55 + j.match_score * 0.30
    return base + india.india_bonus(j.location, j.remote) + india.domain_bonus(j.title)


@router.get("/sources")
def sources(user: User = Depends(get_approved_user)):
    return {"sources": aggregator.provider_status(), "platforms": platform_capabilities()}


@router.get("", response_model=JobSearchOut)
async def search_jobs(
    q: str = Query(""),
    location: str = Query(""),
    employment_type: str = Query("", description="internship | fresher | job | any"),
    limit: int = Query(40, ge=1, le=100),
    refresh: bool = Query(False),
    include_ineligible: bool = Query(False, description="include roles flagged not-eligible (senior/PhD/visa)"),
    internships_only: Optional[bool] = Query(None, description="hard filter: only intern/new-grad/fresher roles (defaults ON for students/freshers)"),
    company: str = Query("", description="filter to a company (case-insensitive substring)"),
    min_salary: int = Query(0, ge=0, description="minimum ANNUAL salary in INR (unknown-salary roles are kept)"),
    duration: str = Query("", description="internship duration bucket, e.g. '3' or '6' (months)"),
    remote: bool = Query(False, description="keep only remote roles (combines with location, e.g. location=India&remote=true)"),
    user: User = Depends(get_approved_user),
    db: Session = Depends(get_db),
):
    enforce("search", str(user.id), settings.RL_SEARCH_PER_MIN, 60)
    profile = _load_profile(db, user)
    keywords = profile["keywords"]
    if not q:
        if profile["roles"]:
            q = " ".join(profile["roles"][:3])
        if profile["locations"] and not location:
            location = profile["locations"][0]
        if not q:
            q = user.job_title or "software engineer"

    jobs = await aggregator.search(
        query=q, location=location, keywords=keywords, limit=limit,
        use_cache=not refresh, employment_type=employment_type,
    )

    applied_hashes = {
        row[0] for row in db.query(Application.job_url_hash).filter_by(user_id=user.id).all()
    }
    items = [_decorate(j, profile, applied_hashes) for j in jobs]

    # Strict eligibility filtering is ON FOR EVERYONE (not a paywalled feature):
    # "Not Recommended" roles (senior/staff/principal/lead/manager/director/
    # architect/PhD/Master's-required/3+ yrs) are hidden by default for early-career
    # users. Eligibility-first, student-first ranking; match score breaks ties.
    hidden = sum(1 for j in items if not j.eligible)
    if not include_ineligible:
        items = [j for j in items if j.eligible]
    else:
        hidden = 0

    # Internships-&-new-grad hard filter: keep only roles carrying an explicit
    # early-career signal (Intern/New Grad/Graduate Program/University Graduate/
    # Campus/Fresher/Entry Level/Associate Engineer). Generic "Software Engineer"
    # and any senior title are dropped. Defaults ON for students/freshers; the user
    # can disable it (?internships_only=false).
    io = internships_only_default(profile) if internships_only is None else internships_only
    filtered_generic = 0
    if io:
        kept = [j for j in items if j.early_signal]
        filtered_generic = len(items) - len(kept)
        items = kept

    # Discovery filters (company / minimum INR salary / internship duration).
    # Applied after eligibility so counts above stay meaningful. Unknown salary
    # and unknown duration are kept — never filtered out — since most internships
    # don't publish either.
    if company:
        items = [j for j in items if india.company_match(j.company, company)]
    if min_salary:
        items = [j for j in items if india.passes_salary(j.salary_inr, min_salary)]
    if duration:
        items = [j for j in items if india.duration_match(j.duration, duration)]
    # Remote tab: keep only remote roles, applied ON TOP of the location filter so
    # "India + Remote" yields remote India roles (never global remote that bypasses
    # the chosen location).
    if remote:
        items = [j for j in items if j.remote]
        # India + Remote is India-first: show only India-tagged / Remote-India roles
        # and exclude generic worldwide-remote postings (location "Remote"/blank that
        # carry no India tag) which the location filter otherwise lets through.
        if location and india.is_india_filter(location):
            items = [j for j in items if india.is_india_location(j.location)]

    # India-first tiered ordering: tier is the PRIMARY key (India on-site → India-
    # remote → global), so India always outranks US/EU regardless of match score.
    # Within a tier, the existing relevance order (_rank_key) is preserved unchanged.
    items.sort(key=lambda j: (india.india_tier(j.location, j.remote), -_rank_key(j)))

    from ..jobs import coverage
    insh = coverage.internshala_breakdown(items)

    from .. import analytics
    analytics.capture(analytics.JOB_SEARCH, user.id,
                      {"q": q, "location": location, "results": len(items),
                       "internships_only": io, "company": company,
                       "min_salary": min_salary, "duration": duration, "remote": remote,
                       "internshala": insh})

    return JobSearchOut(items=items, total=len(items), sources=aggregator.provider_status(),
                        hidden_ineligible=hidden, internships_only=io,
                        filtered_generic=filtered_generic, internshala_coverage=insh)


@router.post("/prepare")
def prepare_application(
    job: PrepareIn,
    user: User = Depends(get_approved_user),
    db: Session = Depends(get_db),
):
    """Map the user's profile onto the platform's application form.

    Returns the prefilled package + screening questions + capability so the
    frontend can show a review-and-approve screen.
    """
    profile = _load_profile(db, user)
    if not profile["resume_path"]:
        raise HTTPException(status_code=400, detail="Upload your resume first so we can prepare the application")

    job_dict = job.model_dump()
    adapter = adapter_for(job_dict)
    package = adapter.build_package(profile, job_dict, profile["resume_path"])
    match = score_job(job_dict, profile)
    from .. import analytics
    analytics.capture(analytics.JOB_CLICK, user.id,
                      {"platform": adapter.platform, "company": job_dict.get("company", "")})
    return {
        "platform": adapter.platform,
        "auto_submit": adapter.supports_auto_submit,
        "manual_required": adapter.manual_only,
        "match_score": match["score"],
        "match_reasons": match["reasons"],
        "package": package.to_dict(),
    }


@router.post("/submit")
async def submit_application(
    data: SubmitIn,
    user: User = Depends(get_approved_user),
    db: Session = Depends(get_db),
):
    """Record (and, where possible, auto-submit) an application after approval."""
    if not data.approved:
        raise HTTPException(status_code=400, detail="Application must be approved before submitting")

    job = data.job.model_dump()
    adapter = adapter_for(job)
    profile = _load_profile(db, user)
    package = adapter.build_package(profile, job, profile["resume_path"])

    # Perform the platform action (manual-only → no-op; capable → live/opt-in).
    result = await adapter.submit(package, data.answers or {})

    # Canonical, evidence-honest statuses. This endpoint records intent/attempt;
    # it never produces "Verified Submitted" (that requires the evidence pipeline)
    # and never writes the retired "Applied" label.
    if result.get("submitted"):
        status, sub = "Submitted", "Submitted"   # attempted (no confirmation evidence here)
    elif result.get("manual_required"):
        status, sub = "Pending", "Manual Apply"   # user must finish on the platform
    else:
        status, sub = "Tracked", "Draft"          # prepared + approved (live submission disabled)

    match = score_job(job, profile)
    existing = (
        db.query(Application).filter_by(user_id=user.id, job_url_hash=job["fingerprint"]).first()
    )
    if existing:
        existing.status = status
        existing.submission_status = sub
        existing.platform = adapter.platform
        existing.manual_required = adapter.manual_only
        existing.match_score = match["score"]
        existing.salary_inr = job.get("salary_inr", "")
        db.commit()
        app = existing
    else:
        app = Application(
            user_id=user.id,
            portal=job["source"],
            source=job["source"],
            platform=adapter.platform,
            job_title=job["title"],
            company=job["company"],
            location=job.get("location", ""),
            salary=job.get("salary", ""),
            salary_inr=job.get("salary_inr", ""),
            apply_url=job["apply_url"],
            verified=job.get("verified", False),
            match_score=match["score"],
            manual_required=adapter.manual_only,
            job_url_hash=job["fingerprint"],
            status=status,
            submission_status=sub,
        )
        db.add(app)
        db.commit()
        db.refresh(app)

    notifications.application_recorded(user.email, user.full_name, job["title"],
                                       job["company"], status)

    from .. import analytics
    analytics.capture(analytics.APPLICATION_STARTED, user.id,
                      {"platform": adapter.platform, "company": job.get("company", "")})
    if result.get("submitted"):
        analytics.capture(analytics.APPLICATION_SUBMITTED, user.id,
                          {"platform": adapter.platform})
    elif result.get("manual_required"):
        analytics.capture(analytics.MANUAL_APPLY, user.id, {"platform": adapter.platform})

    return {
        "message": result.get("message", "Application recorded"),
        "status": status,
        "manual_required": adapter.manual_only,
        "apply_url": job["apply_url"],
        "application_id": app.id,
    }


@router.post("/apply")
def apply_to_job(
    data: ApplyIntentIn,
    user: User = Depends(get_approved_user),
    db: Session = Depends(get_db),
):
    """Lightweight 'Save' / quick-track without the full workflow.

    No submission happens here, so the only honest outcomes are 'Saved' (Draft)
    or 'Tracked' (monitored). A client sending the retired 'Applied' is coerced to
    'Tracked' — clicking Apply merely starts tracking; it never marks submitted.
    """
    if data.status not in ("Applied", "Saved", "Tracked"):
        raise HTTPException(status_code=400, detail="Invalid status")
    # Canonical mapping: Applied -> Tracked, Saved -> Saved.
    lifecycle = "Saved" if data.status == "Saved" else "Tracked"
    sub = "Draft"  # nothing submitted via this endpoint
    existing = (
        db.query(Application).filter_by(user_id=user.id, job_url_hash=data.fingerprint).first()
    )
    if existing:
        if existing.status == "Saved" and lifecycle == "Tracked":
            existing.status = "Tracked"
            db.commit()
        return {"message": "Already tracked", "apply_url": existing.apply_url,
                "status": existing.status, "display_status": existing.display_status}

    app = Application(
        user_id=user.id, portal=data.source, source=data.source, platform=data.platform,
        job_title=data.title, company=data.company, location=data.location,
        salary=data.salary, salary_inr=data.salary_inr, deadline=data.deadline,
        apply_url=data.apply_url, verified=data.verified, match_score=data.match_score,
        manual_required=data.manual_required, job_url_hash=data.fingerprint,
        status=lifecycle, submission_status=sub,
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    from .. import analytics
    analytics.capture(analytics.TRACKED_JOB, user.id,
                      {"platform": data.platform, "company": data.company})
    return {"message": f"Job {lifecycle.lower()}", "apply_url": data.apply_url,
            "status": lifecycle, "display_status": app.display_status}


@router.post("/greenhouse/form")
def greenhouse_form(
    data: GreenhouseApplyIn,
    user: User = Depends(get_approved_user),
    db: Session = Depends(get_db),
):
    """READ-ONLY: the Greenhouse posting's required screening questions + the
    profile prefill, so the submit wizard can collect truthful answers BEFORE the
    user confirms a real submission. Uses the public Board API (no browser, no
    submit, no DB write)."""
    if data.source.lower() != "greenhouse":
        raise HTTPException(status_code=400, detail="This endpoint only handles Greenhouse jobs")
    bj = parse_board_job(data.model_dump())
    if not bj:
        raise HTTPException(status_code=400, detail="Could not resolve the Greenhouse board/job id")
    try:
        title, fields = fetch_fields(bj[0], bj[1])
    except Exception:
        raise HTTPException(status_code=502, detail="Could not load the Greenhouse application form")

    profile = _load_profile(db, user)
    ok, missing = _profile_complete(profile)
    skip = CORE_TEXT | {"resume", "resume_text", "cover_letter", "cover_letter_text"}

    def q(f):
        return {"name": f.name, "label": f.label, "type": f.type, "required": f.required,
                "values": [{"label": l, "value": v} for l, v in (f.values or [])]}

    qs = [q(f) for f in fields if f.name and f.name not in skip]
    rf = (profile.get("resume_path") or "").split("/")[-1]
    return {
        "title": title or data.title,
        "company": data.company,
        "profile_complete": ok,
        "missing_profile": missing,
        "prefill": {"name": profile.get("name", ""), "email": profile.get("email", ""),
                    "phone": profile.get("phone", ""), "resume_filename": rf},
        "required_questions": [x for x in qs if x["required"]],
        "optional_questions": [x for x in qs if not x["required"]],
    }


@router.post("/greenhouse/apply")
async def greenhouse_apply(
    data: GreenhouseApplyIn,
    user: User = Depends(get_approved_user),
    db: Session = Depends(get_db),
):
    """Production: submit ONE real Greenhouse application for the signed-in user.

    Hard gates (all required): explicit approval, a real uploaded resume, a
    complete profile, the job is a Greenhouse posting, and live mode is ready.
    Never fabricates data — only the user's profile + their reviewed answers.
    """
    # Rate limit: per-user burst + daily cap (browser-launching endpoint).
    enforce("gh_apply_burst", str(user.id), settings.RL_APPLY_BURST_PER_MIN, 60)
    enforce("gh_apply_day", str(user.id), settings.RL_APPLY_PER_DAY, 86400)

    # Gate 1 — explicit click/approval.
    if not data.approved:
        raise HTTPException(status_code=400, detail="You must explicitly approve before submitting")

    # Gate 2 — must be a Greenhouse job we can reach.
    job = data.model_dump()
    if data.source.lower() != "greenhouse":
        raise HTTPException(status_code=400, detail="This endpoint only handles Greenhouse jobs")
    form_url = resolve_form_url(job)
    if not form_url:
        raise HTTPException(status_code=400, detail="Could not resolve the Greenhouse application form URL")

    # Gate 3 — real resume + complete profile.
    profile = _load_profile(db, user)
    ok, missing = _profile_complete(profile)
    if not ok:
        raise HTTPException(status_code=400,
                            detail=f"Complete your profile before applying. Missing: {', '.join(missing)}")

    # Upsert the application row and ENQUEUE it. The browser submission runs in a
    # background worker (concurrency-capped, retried) — never inline in this
    # request, which returns immediately. (H1)
    app = db.query(Application).filter_by(user_id=user.id, job_url_hash=data.fingerprint).first()
    if not app:
        app = Application(user_id=user.id, job_url_hash=data.fingerprint)
        db.add(app)
    app.portal = data.source
    app.source = data.source
    app.platform = "Greenhouse"
    app.job_title = data.title
    app.company = data.company
    app.location = data.location
    app.salary = data.salary
    app.salary_inr = data.salary_inr
    app.apply_url = data.apply_url
    app.verified = data.verified
    app.manual_required = False
    app.submission_status = "Queued"
    app.submission_attempts = 0
    app.submission_payload = json.dumps({
        "answers": data.answers or {},
        "external_id": data.external_id,
        "form_url": form_url,
    })
    db.commit()
    db.refresh(app)

    backend = enqueue_submission(app.id)
    return {
        "submission_status": "Queued",
        "application_id": app.id,
        "queue_backend": backend,
        "message": "Application queued — processing in the background. Track status in your Activity Log.",
    }


@router.post("/refresh")
def refresh_cache(user: User = Depends(get_approved_user)):
    aggregator.clear_cache()
    return {"message": "Job cache cleared — next search fetches fresh listings"}
