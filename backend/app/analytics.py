"""Product analytics — thin PostHog wrapper, fully gated.

`capture()` is a no-op unless `POSTHOG_API_KEY` is set (and the `posthog` package
is installed), so it is safe to call from anywhere with zero overhead in dev. It
never raises — analytics must never break a request. Events are sent in a
background thread by the PostHog client.

Tracked beta events (canonical names):
  signup · resume_uploaded · job_search · application_started ·
  application_submitted · verified_submitted · feedback_submitted ·
  upgrade_started · subscription_activated
"""
from __future__ import annotations

import logging

from .config import settings

log = logging.getLogger("jobara.analytics")

_client = None
_init = False

# Canonical event names (use these constants at call sites).
SIGNUP = "signup"
LOGIN = "login"
RESUME_UPLOADED = "resume_uploaded"
JOB_SEARCH = "job_search"
JOB_CLICK = "job_click"
TRACKED_JOB = "tracked_job"
MANUAL_APPLY = "manual_apply"
APPLICATION_STARTED = "application_started"
APPLICATION_SUBMITTED = "application_submitted"
VERIFIED_SUBMITTED = "verified_submitted"
FEEDBACK_SUBMITTED = "feedback_submitted"


def _get_client():
    global _client, _init
    if _init:
        return _client
    _init = True
    if not settings.POSTHOG_API_KEY:
        return None
    try:
        from posthog import Posthog
        _client = Posthog(project_api_key=settings.POSTHOG_API_KEY,
                          host=settings.POSTHOG_HOST)
        log.info("PostHog analytics enabled")
    except Exception as e:  # package missing or bad config — stay silent
        log.warning(f"PostHog init failed ({e}); analytics disabled")
        _client = None
    return _client


def capture(event: str, distinct_id, properties: dict | None = None) -> None:
    """Fire-and-forget event. No-op when analytics is unconfigured. Never raises."""
    client = _get_client()
    if client is None:
        return
    try:
        client.capture(distinct_id=str(distinct_id), event=event,
                       properties={"$lib": "jobora-server", **(properties or {})})
    except Exception as e:
        log.debug(f"analytics capture failed: {e}")


def enabled() -> bool:
    return _get_client() is not None
