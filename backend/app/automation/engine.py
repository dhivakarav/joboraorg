"""Auto-apply engine.

Hands-off pipeline: scan the user's resume-derived profile → discover real
matching jobs → for each job, select the platform adapter and APPLY:

  * auto-capable platforms (Greenhouse, Lever, Ashby, Workable): the adapter
    prepares + submits the application. Real browser submission happens when
    JOBORA_LIVE=1; otherwise the application is prepared, approved, and recorded.
  * manual-only platforms (LinkedIn, Workday, company career pages): recorded as
    "Pending — Manual Apply Required" with the real application URL.

Respects the daily limit, skips duplicates, and streams progress over SSE.
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict

from ..adapters import adapter_for
from ..database import SessionLocal
from ..jobs import aggregator
from ..jobs.base import is_specific_job_url
from .matcher import score_job   # single resume↔job match engine
from ..models import Application, JobFilter, Resume, User

_tasks: Dict[int, asyncio.Task] = {}
_queues: Dict[int, asyncio.Queue] = {}


def get_queue(user_id: int) -> asyncio.Queue:
    if user_id not in _queues:
        _queues[user_id] = asyncio.Queue()
    return _queues[user_id]


def is_running(user_id: int) -> bool:
    task = _tasks.get(user_id)
    return task is not None and not task.done()


async def _emit(user_id: int, event: dict):
    event["ts"] = datetime.utcnow().isoformat()
    await get_queue(user_id).put(event)


def _load_context(user_id: int) -> dict:
    db = SessionLocal()
    try:
        filt = db.query(JobFilter).filter_by(user_id=user_id).first()
        resume = db.query(Resume).filter_by(user_id=user_id).first()
        user = db.query(User).filter_by(id=user_id).first()

        roles = json.loads(filt.roles) if filt and filt.roles else []
        keywords = json.loads(filt.keywords) if filt and filt.keywords else []
        locations = json.loads(filt.locations) if filt and filt.locations else []
        daily_limit = filt.daily_limit if filt else 20
        # Same resume match-score floor used by Find Jobs / Matched Jobs — one
        # threshold, respected everywhere (default 50 when unset).
        min_match = filt.min_match_score if (filt and filt.min_match_score is not None) else 50
        query = " ".join(roles[:3]) or (user.job_title if user else "") or "software engineer"
        location = locations[0] if locations else ""

        skills = json.loads(resume.parsed_skills) if resume and resume.parsed_skills else []
        profile = {
            "name": (resume.parsed_name if resume else "") or (user.full_name if user else ""),
            "email": (resume.parsed_email if resume else "") or (user.email if user else ""),
            "phone": (resume.parsed_phone if resume else "") or (user.phone if user else ""),
            "location": (resume.parsed_location if resume else "") or "",
            "linkedin_url": resume.linkedin_url if resume else "",
            "portfolio_url": resume.portfolio_url if resume else "",
            "skills": skills,
            "experience": (resume.parsed_experience if resume else 0) or (user.years_experience if user else 0),
            "roles": roles, "keywords": keywords, "locations": locations,
        }
        resume_path = resume.file_path if resume else ""

        since = datetime.utcnow() - timedelta(hours=24)
        applied_today = (
            db.query(Application)
            .filter(Application.user_id == user_id, Application.applied_at >= since)
            .count()
        )
        existing = {
            row[0] for row in db.query(Application.job_url_hash).filter_by(user_id=user_id).all()
        }
        return {
            "query": query, "location": location, "keywords": keywords,
            "daily_limit": daily_limit, "min_match": min_match,
            "applied_today": applied_today,
            "existing": existing, "profile": profile, "resume_path": resume_path,
        }
    finally:
        db.close()


# Map an engine outcome onto (internal lifecycle, canonical submission_status).
# A real auto-submit now CAN capture confirmation evidence (screenshot + id +
# confirmation URL); when all three are present the row graduates to "Verified
# Submitted". The retired "Applied" label is never written.
_CANON = {
    "Pending Approval": ("Pending", "Pending Approval"),  # awaiting user confirm — NOT submitted
    "Submitted":    ("Submitted", "Submitted"),     # attempted (evidence may upgrade it)
    "Manual Apply": ("Pending",   "Manual Apply"),
    "Failed":       ("Pending",   "Failed"),
    "Tracked":      ("Tracked",   "Draft"),
}


def _store_evidence(app, result: dict):
    """Persist post-submit evidence (screenshot + id + confirmation URL) onto the
    application and upgrade it to Verified Submitted when all three exist."""
    import json
    from ..storage import storage
    ev = {}
    shot = (result or {}).get("screenshot_path")
    if shot:
        try:
            key = f"evidence/{app.id}/screenshot_{datetime.utcnow().timestamp():.0f}.png"
            storage.save_file(key, shot)
            ev["screenshot_key"] = key
        except Exception:
            pass
    app.application_id = (result or {}).get("application_id", "") or ""
    app.external_application_id = app.application_id
    app.confirmation_url = (result or {}).get("confirmation_url", "") or ""
    if result and result.get("platform_response"):
        ev["platform_response"] = result["platform_response"][:1500]
    app.submission_evidence = json.dumps(ev)
    app.evidence_available = bool(ev.get("screenshot_key"))
    # INTEGRITY GATE: Verified requires id + confirmation_url + a stored artifact.
    if app.application_id and app.confirmation_url and app.evidence_available:
        app.submission_status = "Verified Submitted"
        app.submitted_at = datetime.utcnow()


def _record(user_id: int, job: dict, adapter, status: str, match: int, result: dict = None):
    lifecycle, sub = _CANON.get(status, ("Tracked", "Draft"))
    db = SessionLocal()
    try:
        app = Application(
            user_id=user_id,
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
            match_score=match,
            manual_required=adapter.manual_only,
            job_url_hash=job["fingerprint"],
            status=lifecycle,
            submission_status=sub,
        )
        db.add(app)
        db.flush()   # assign app.id for the evidence key
        if status == "Submitted" and result:
            _store_evidence(app, result)
        db.commit()
        return app.submission_status
    finally:
        db.close()


def _pending_count(user_id: int) -> int:
    """How many jobs are currently waiting for the user's approval (all runs)."""
    db = SessionLocal()
    try:
        return (db.query(Application)
                .filter_by(user_id=user_id, submission_status="Pending Approval").count())
    finally:
        db.close()


async def _run(user_id: int):
    ctx = _load_context(user_id)
    limit = ctx["daily_limit"]
    profile = ctx["profile"]
    applied = 0
    seen = set(ctx["existing"])

    if not ctx["resume_path"]:
        await _emit(user_id, {"type": "error",
                              "message": "Upload your resume first so we can auto-apply."})
        await _emit(user_id, {"type": "done", "message": "Stopped."})
        return

    await _emit(user_id, {"type": "start",
                          "message": f"Scanning sources and matching jobs for “{ctx['query']}”"
                                     + (f" in {ctx['location']}" if ctx["location"] else "")
                                     + " — auto-apply jobs will be queued for your approval.",
                          "daily_limit": limit})
    try:
        await _emit(user_id, {"type": "portal", "message": "Discovering matching jobs…"})
        jobs = await aggregator.search(query=ctx["query"], location=ctx["location"],
                                       keywords=ctx["keywords"], limit=limit * 3, use_cache=True)
        if not jobs:
            for fb in ("software engineer", "developer", "engineer", "analyst"):
                await _emit(user_id, {"type": "info",
                                      "message": f"No matches for “{ctx['query']}” — broadening to “{fb}”…"})
                jobs = await aggregator.search(query=fb, location="", keywords=[],
                                               limit=limit * 3, use_cache=True)
                if jobs:
                    break

        # Score, then APPLY THE MATCH-SCORE THRESHOLD (same one Find Jobs / Matched
        # Jobs use). Jobs below the user's min_match_score never enter the queue.
        from ..jobs.eligibility import eligibility
        min_match = ctx["min_match"]
        scored = [(score_job(j, profile)["score"], j) for j in jobs]
        scored.sort(key=lambda t: t[0], reverse=True)
        before = len(scored)
        scored = [(s, j) for s, j in scored if s >= min_match]
        # ELIGIBILITY FILTER — same gate Find Jobs applies: never auto-queue roles
        # flagged Not Recommended for this profile (senior / staff / principal / lead
        # / manager / director / VP / architect / PhD-required / 3+ yrs). This is
        # what stops senior-staff roles (e.g. Druva "Senior Staff Software Engineer")
        # from being queued for auto-apply in the first place.
        after_match = len(scored)
        scored = [(s, j) for s, j in scored if eligibility(j, profile)["eligible"]]
        skipped_ineligible = after_match - len(scored)
        await _emit(user_id, {"type": "info",
                              "message": f"{before} openings found; {len(scored)} meet your "
                                         f"{min_match}% match threshold and eligibility"
                                         + (f" ({skipped_ineligible} senior/not-recommended "
                                            f"role(s) skipped)" if skipped_ineligible else "")
                                         + f". Reviewing top {limit}…"})

        skipped_seen = 0   # met the threshold but already tracked from a previous run
        new_pending = 0    # auto-capable (Greenhouse) → Pending Approval queue
        new_manual = 0     # manual/assisted (Lever/Ashby/etc.) → Matched Jobs
        for match, job in scored:
            if applied >= limit:
                break
            if job["fingerprint"] in seen:
                skipped_seen += 1
                continue
            # Only surface rows that link to a SPECIFIC job page — never a generic
            # search/listing/homepage URL.
            if not is_specific_job_url(job.get("apply_url", "")):
                continue
            seen.add(job["fingerprint"])

            adapter = adapter_for(job)
            # SAFETY GATE: "Start Applying" NEVER auto-submits to a real company.
            # Only auto-capable adapters (Greenhouse) are queued as "Pending Approval"
            # for the user to review + confirm. Manual/assisted adapters (Lever,
            # Ashby, Internshala, …) go to Matched Jobs — they never enter the queue.
            if adapter.supports_auto_submit and not adapter.manual_only:
                status = "Pending Approval"
                new_pending += 1
            else:
                status = "Manual Apply"
                new_manual += 1
            _record(user_id, job, adapter, status, match)
            applied += 1
            await _emit(user_id, {
                "type": "log", "portal": adapter.platform, "job_title": job["title"],
                "company": job["company"], "location": job.get("location", ""),
                "salary": job.get("salary_inr", ""), "match": match,
                "manual_required": adapter.manual_only, "verified": job.get("verified", False),
                "status": status, "applied_today": applied,
                "apply_url": job["apply_url"],
            })
            await asyncio.sleep(0.1)

        # NOTE: we deliberately do NOT generate generic "[role] on Naukri/Unstop/…"
        # search-link rows. Every surfaced row must point to a real, SPECIFIC job
        # application page — manual-apply portals only appear when a licensed
        # aggregator (JSearch/Adzuna) actually returned a specific listing whose
        # apply_url is that portal (handled in the scored loop above).

        # Count what's actually waiting for the user now (this run + earlier runs).
        pending_total = _pending_count(user_id)
        meet = len(scored)
        if applied:
            new_msg = (f"{applied} new match(es): {new_pending} auto-apply → Pending Approval, "
                       f"{new_manual} manual → Matched Jobs"
                       + (f"; {skipped_seen} already tracked from a previous run" if skipped_seen else ""))
        elif meet:
            new_msg = (f"{meet} job(s) meet your {min_match}% threshold, but 0 are new — "
                       f"all {skipped_seen} were already tracked from a previous run")
        else:
            new_msg = f"no jobs met your {min_match}% match threshold"
        await _emit(user_id, {
            "type": "done", "applied_today": applied,
            "message": (f"Done. {new_msg}. "
                        f"You have {pending_total} job(s) awaiting approval. "
                        f"Manual-apply matches (with real listing links) are in Matched Jobs. "
                        f"Nothing was submitted to any company.")})
    except asyncio.CancelledError:
        await _emit(user_id, {"type": "done", "applied_today": applied, "message": "Stopped by user."})
        raise
    except Exception as exc:
        await _emit(user_id, {"type": "error", "message": f"Auto-apply error: {exc}"})
        await _emit(user_id, {"type": "done", "applied_today": applied, "message": "Stopped."})


def start(user_id: int) -> bool:
    if is_running(user_id):
        return False
    _queues[user_id] = asyncio.Queue()
    _tasks[user_id] = asyncio.create_task(_run(user_id))
    return True


async def stop(user_id: int) -> bool:
    task = _tasks.get(user_id)
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return True
    return False
