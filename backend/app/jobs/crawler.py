"""Crawl-and-store engine — an in-app async loop.

Repeatedly queries the free provider APIs across a (query × country) matrix and
upserts every unique job into the CrawledJob store. Over time this accumulates a
large pool (10k+) while search shows only the top few hundred by match score.

Runtime: a single asyncio background task started from the app lifespan, gated by
CRAWLER_ENABLED so it never runs in tests. Pacing keeps it under free-tier
provider quotas. No Redis/cron/Docker required.
"""
from __future__ import annotations

import asyncio
import logging

from ..config import settings
from ..database import SessionLocal
from . import aggregator
from .store import upsert_jobs, count_stored

log = logging.getLogger("jobora.crawler")

# Country code → location string the providers understand.
COUNTRIES: dict[str, str] = {
    "in": "India",
    "us": "United States",
    "ca": "Canada",
    "gb": "United Kingdom",
    "de": "Germany",
    "sg": "Singapore",
    "ae": "United Arab Emirates",
    "remote": "",  # remote-first: no location filter, remote flag emphasised
}

DEFAULT_QUERIES = [
    "embedded designer", "embedded engineer", "embedded systems",
    "firmware engineer", "hardware engineer", "vlsi",
    "software engineer", "backend engineer", "data engineer",
    "machine learning engineer", "ai engineer",
]


def _queries() -> list[str]:
    raw = (settings.CRAWLER_QUERIES or "").strip()
    if raw:
        return [q.strip() for q in raw.split(",") if q.strip()]
    return DEFAULT_QUERIES


def _countries() -> list[str]:
    raw = (settings.CRAWLER_COUNTRIES or "").strip()
    codes = [c.strip().lower() for c in raw.split(",") if c.strip()] if raw else list(COUNTRIES)
    return [c for c in codes if c in COUNTRIES]


async def crawl_once() -> dict:
    """One full sweep of the query × country matrix. Returns a summary dict."""
    queries = _queries()
    countries = _countries()
    total_ins = total_upd = 0
    for code in countries:
        location = COUNTRIES[code]
        for q in queries:
            try:
                jobs = await aggregator.search(
                    query=q,
                    location=location,
                    keywords=[],
                    limit=settings.CRAWLER_PER_QUERY_LIMIT,
                    use_cache=True,
                    recent=False,
                )
                if code == "remote":
                    jobs = [j for j in jobs if j.get("remote")]
                db = SessionLocal()
                try:
                    ins, upd = upsert_jobs(db, jobs, country=code, query=q)
                finally:
                    db.close()
                total_ins += ins
                total_upd += upd
                log.info("crawl %s/%r → +%d new, %d seen", code, q, ins, upd)
            except Exception as exc:  # never let one combo kill the sweep
                log.warning("crawl %s/%r failed: %s", code, q, exc)
            # Pace between provider calls to respect free-tier quotas.
            await asyncio.sleep(settings.CRAWLER_PACING_SEC)

    db = SessionLocal()
    try:
        pool = count_stored(db)
    finally:
        db.close()
    log.info("crawl sweep done: +%d new, %d re-seen, pool=%d", total_ins, total_upd, pool)
    return {"inserted": total_ins, "updated": total_upd, "pool": pool}


async def _loop() -> None:
    # Small delay so app startup finishes before the first heavy sweep.
    await asyncio.sleep(5)
    while True:
        try:
            await crawl_once()
        except Exception as exc:
            log.warning("crawl sweep errored: %s", exc)
        await asyncio.sleep(settings.CRAWLER_INTERVAL_MIN * 60)


_task: asyncio.Task | None = None


def start_crawler() -> None:
    """Start the background crawl loop if enabled. Safe to call once at startup."""
    global _task
    if not settings.CRAWLER_ENABLED:
        log.info("crawler disabled (set CRAWLER_ENABLED=1 to enable)")
        return
    if _task and not _task.done():
        return
    try:
        _task = asyncio.get_event_loop().create_task(_loop())
        log.info("crawler started: every %d min, queries=%d, countries=%d",
                 settings.CRAWLER_INTERVAL_MIN, len(_queries()), len(_countries()))
    except RuntimeError:
        # No running loop (e.g. imported outside the server) — skip.
        log.info("crawler not started: no running event loop")
