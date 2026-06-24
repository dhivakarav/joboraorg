"""Background submission queue (H1).

Greenhouse submissions no longer run inside the HTTP request. The API enqueues
an application id and returns immediately ("Queued"); a worker processes jobs
with a **concurrency cap** (so we never launch unbounded browsers) and **retries
transient failures** with backoff.

Two execution modes share the same `process_submission(app_id)`:
  - **In-process** (default / dev / single node): an asyncio worker started in
    the app lifespan, bounded by a semaphore.
  - **Redis (RQ)** (production multi-node): set REDIS_URL and run a separate
    `rq worker` consuming the "submissions" queue; the API enqueues a job that
    calls `run_submission_sync(app_id)`. Concurrency = number of RQ workers.

Either way the request thread never blocks on a browser.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from .config import settings
from .database import SessionLocal
from .models import Application, User

log = logging.getLogger("jobara.queue")

# Errors we consider transient (worth retrying).
_TRANSIENT = ("timeout", "timederror", "connection", "econnreset", "temporarily",
              "navigation", "net::", "reset by peer")

_inproc_queue: "Optional[asyncio.Queue[int]]" = None
_semaphore: Optional[asyncio.Semaphore] = None
_started = False


# ---------------------------------------------------------------- enqueue
def enqueue(app_id: int) -> str:
    """Enqueue a submission. Returns the backend used ('redis' or 'inprocess')."""
    if settings.REDIS_URL:
        try:
            from redis import Redis
            from rq import Queue
            q = Queue("submissions", connection=Redis.from_url(settings.REDIS_URL))
            q.enqueue("app.queue.run_submission_sync", app_id, job_timeout=600)
            return "redis"
        except Exception as exc:
            log.error(f"RQ enqueue failed ({exc}); falling back to in-process")
    # in-process
    if _inproc_queue is not None:
        _inproc_queue.put_nowait(app_id)
    else:
        # worker not started (e.g. tests) — run detached
        asyncio.get_event_loop().create_task(_run_one(app_id))
    return "inprocess"


# ---------------------------------------------------------------- worker (in-process)
def start_worker():
    """Start the in-process consumer + concurrency semaphore (call from lifespan)."""
    global _inproc_queue, _semaphore, _started
    if _started or not settings.INPROCESS_WORKER:
        return
    _inproc_queue = asyncio.Queue()
    _semaphore = asyncio.Semaphore(settings.SUBMISSION_CONCURRENCY)
    asyncio.create_task(_consumer())
    _started = True
    log.info(f"submission worker started (concurrency={settings.SUBMISSION_CONCURRENCY})")


async def _consumer():
    while True:
        app_id = await _inproc_queue.get()
        asyncio.create_task(_run_one(app_id))  # bounded inside by the semaphore


async def _run_one(app_id: int):
    if _semaphore is not None:
        async with _semaphore:
            await process_submission(app_id)
    else:
        await process_submission(app_id)


# ---------------------------------------------------------------- the job
async def _run_platform_submit(platform: str, app, payload: dict, answers: dict,
                               profile: dict, evidence_dir: str):
    """Dispatch to the right live submitter by platform. Returns an outcome object
    exposing .submission_status, .application_id, .confirmation_url, .evidence_json()."""
    if platform == "Internshala":
        from .adapters.internshala_submit import apply as ish_apply
        from .credentials import get_plaintext
        cdb = SessionLocal()
        try:
            pair = get_plaintext(cdb, app.user_id, "Internshala")
        finally:
            cdb.close()
        username, password = pair if pair else ("", "")
        return await ish_apply(app.apply_url, profile, profile["resume_path"],
                               answers, username, password, evidence_dir, tag="apply")

    # default: Greenhouse
    from .adapters.greenhouse_fill import fetch_fields
    from .adapters.greenhouse_production import apply as gh_apply
    from .adapters.greenhouse_production import parse_board_job, resolve_form_url
    job = {"external_id": payload.get("external_id", ""),
           "apply_url": app.apply_url, "form_url": payload.get("form_url", "")}
    form_url = resolve_form_url(job)
    bj = parse_board_job(job)
    try:
        _, fields = fetch_fields(bj[0], bj[1]) if bj else ("", [])
    except Exception:
        fields = []
    return await gh_apply(form_url, fields, profile, profile["resume_path"],
                          answers, evidence_dir, tag="apply")


async def process_submission(app_id: int):
    """Process one queued application: fill + submit + verify + persist."""
    from .adapters.runtime import live_ready
    from .services import load_profile
    from .storage import storage

    db = SessionLocal()
    try:
        app = db.query(Application).filter_by(id=app_id).first()
        if not app or app.submission_status not in ("Queued", "Processing"):
            return
        user = db.query(User).filter_by(id=app.user_id).first()
        if not user:
            return
        payload = json.loads(app.submission_payload or "{}")
        answers = payload.get("answers", {})

        app.submission_status = "Processing"
        app.submission_attempts = (app.submission_attempts or 0) + 1
        attempt = app.submission_attempts
        db.commit()

        ready, reason = live_ready()
        if not ready:
            app.submission_status = "Manual Apply Required"
            app.status = "Pending"
            app.submission_evidence = json.dumps({"failure_reason": reason})
            db.commit()
            return

        profile = load_profile(db, user)
        evidence_dir = str(settings.UPLOAD_DIR / "evidence" / str(app.id))
        outcome = await _run_platform_submit(app.platform or "Greenhouse", app, payload,
                                             answers, profile, evidence_dir)

        # Push evidence to storage (works for local + S3).
        ev = json.loads(outcome.evidence_json())
        for k in ("screenshot", "html"):
            local = ev.get(k)
            if local:
                try:
                    key = f"evidence/{app.id}/{k}_{datetime.utcnow().timestamp():.0f}" \
                          + (".png" if k == "screenshot" else ".html")
                    storage.save_file(key, local)
                    ev[k + "_key"] = key
                except Exception as e:
                    log.error(f"evidence upload failed: {e}")

        app.external_application_id = outcome.application_id or ""
        app.application_id = outcome.application_id or ""
        app.confirmation_url = outcome.confirmation_url
        app.submission_evidence = json.dumps(ev)
        # Evidence is "available" only if an artifact (screenshot/html) is stored.
        app.evidence_available = bool(ev.get("screenshot") or ev.get("screenshot_key")
                                      or ev.get("html") or ev.get("html_key"))

        sub = outcome.submission_status
        # INTEGRITY GATE: "Verified Submitted" requires id + confirmation_url +
        # a stored evidence artifact. Otherwise it can only be "Submitted".
        if sub == "Verified Submitted" and not (
                app.application_id and app.confirmation_url and app.evidence_available):
            sub = "Submitted"
        app.submission_status = sub

        if sub in ("Verified Submitted", "Submitted"):
            app.submitted_at = datetime.utcnow()
            app.status = "Submitted"   # internal hint; display derives canonical
            _notify(user, app, sub)
        elif outcome.submission_status in ("Failed", "CAPTCHA Required"):
            # Retry only transient failures, and only CAPTCHA never retries.
            transient = _is_transient(outcome.failure_reason) and outcome.submission_status == "Failed"
            if transient and attempt < settings.SUBMISSION_MAX_ATTEMPTS:
                log.info(f"app {app.id} transient failure (attempt {attempt}); retrying")
                app.submission_status = "Queued"
                db.commit()
                await asyncio.sleep(settings.SUBMISSION_RETRY_DELAY)
                enqueue(app.id)
                return
            app.status = "Pending"
        else:
            app.status = "Pending"
        db.commit()
    except Exception as exc:
        log.exception(f"process_submission({app_id}) crashed: {exc}")
        try:
            app = db.query(Application).filter_by(id=app_id).first()
            if app:
                attempt = app.submission_attempts or 0
                if _is_transient(str(exc)) and attempt < settings.SUBMISSION_MAX_ATTEMPTS:
                    app.submission_status = "Queued"
                    db.commit()
                    await asyncio.sleep(settings.SUBMISSION_RETRY_DELAY)
                    enqueue(app_id)
                else:
                    app.submission_status = "Failed"
                    app.status = "Pending"
                    app.submission_evidence = json.dumps({"failure_reason": str(exc)[:300]})
                    db.commit()
        except Exception:
            pass
    finally:
        db.close()


def _is_transient(reason: str) -> bool:
    r = (reason or "").lower()
    return any(t in r for t in _TRANSIENT)


def _notify(user, app, status):
    try:
        from . import notifications
        notifications.application_recorded(user.email, user.full_name,
                                           app.job_title, app.company, status)
    except Exception:
        pass


def run_submission_sync(app_id: int):
    """Sync entrypoint for an RQ worker process."""
    asyncio.run(process_submission(app_id))
