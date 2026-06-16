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
from ..jobs.matching import score_job
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
            "daily_limit": daily_limit, "applied_today": applied_today,
            "existing": existing, "profile": profile, "resume_path": resume_path,
        }
    finally:
        db.close()


# Map an engine outcome onto (internal lifecycle, canonical submission_status).
# This path NEVER captures confirmation evidence, so it can never be "Verified
# Submitted" and never writes the retired "Applied" label.
_CANON = {
    "Submitted":    ("Submitted", "Submitted"),     # attempted (no evidence here)
    "Manual Apply": ("Pending",   "Manual Apply"),
    "Failed":       ("Pending",   "Failed"),
    "Tracked":      ("Tracked",   "Draft"),
}


def _record(user_id: int, job: dict, adapter, status: str, match: int):
    lifecycle, sub = _CANON.get(status, ("Tracked", "Draft"))
    db = SessionLocal()
    try:
        db.add(Application(
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
        ))
        db.commit()
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
                          "message": f"Scanning profile and auto-applying for “{ctx['query']}”"
                                     + (f" in {ctx['location']}" if ctx["location"] else ""),
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

        # Best matches first.
        scored = [(score_job(j, profile)["score"], j) for j in jobs]
        scored.sort(key=lambda t: t[0], reverse=True)
        await _emit(user_id, {"type": "info",
                              "message": f"{len(scored)} matching openings found. Applying to top {limit}…"})

        for match, job in scored:
            if applied >= limit:
                break
            if job["fingerprint"] in seen:
                continue
            seen.add(job["fingerprint"])

            adapter = adapter_for(job)
            package = adapter.build_package(profile, job, ctx["resume_path"])
            try:
                result = await adapter.submit(package, {})
            except Exception as exc:
                await _emit(user_id, {"type": "log", "portal": adapter.platform,
                                      "job_title": job["title"], "company": job["company"],
                                      "location": job.get("location", ""), "status": "Failed",
                                      "message": str(exc)})
                _record(user_id, job, adapter, "Failed", match)
                applied += 1
                continue

            if result.get("submitted"):
                status = "Submitted"
            elif result.get("manual_required"):
                status = "Manual Apply"   # manual apply required
            else:
                status = "Tracked"        # prepared + approved (live disabled) — never "Applied"

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
            await asyncio.sleep(0.15)

        await _emit(user_id, {"type": "done", "applied_today": applied,
                              "message": f"Done. Auto-applied to {applied} job(s). "
                                         f"Review them in your Activity Log."})
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
