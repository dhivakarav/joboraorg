"""Persistent job store for the crawl-and-store engine.

The crawler pushes aggregator results here; upsert dedupes by a normalized
apply-URL hash so the same listing arriving from multiple providers collapses to
one row. Search reads back a scored, ranked slice — the pool keeps growing while
only the top few hundred are shown.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import CrawledJob
from .aggregator import _canonical_url


def url_hash(apply_url: str) -> str:
    """Stable dedupe key: sha256 of the canonicalized apply URL."""
    canon = _canonical_url(apply_url)
    return hashlib.sha256(canon.encode()).hexdigest() if canon else ""


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def upsert_jobs(db: Session, jobs: list[dict], country: str = "", query: str = "") -> tuple[int, int]:
    """Insert new jobs, bump last_seen on ones already stored.

    Returns (inserted, updated). Dedup is by url_hash within the incoming batch
    and against the DB.
    """
    inserted = updated = 0
    seen_in_batch: set[str] = set()

    # Pre-load existing hashes for this batch in one query.
    hashes = []
    prepared = []
    for j in jobs:
        h = url_hash(j.get("apply_url", ""))
        if not h or h in seen_in_batch:
            continue
        seen_in_batch.add(h)
        hashes.append(h)
        prepared.append((h, j))

    if not prepared:
        return (0, 0)

    existing = {
        row[0]
        for row in db.query(CrawledJob.url_hash).filter(CrawledJob.url_hash.in_(hashes)).all()
    }

    now = _now()
    for h, j in prepared:
        if h in existing:
            db.query(CrawledJob).filter(CrawledJob.url_hash == h).update(
                {"last_seen": now}, synchronize_session=False
            )
            updated += 1
            continue
        db.add(CrawledJob(
            url_hash=h,
            title=j.get("title", "")[:500],
            company=j.get("company", "")[:300],
            location=j.get("location", "")[:300],
            country=country,
            description=(j.get("description_snippet", "") or "")[:2000],
            salary=j.get("salary", "")[:200],
            employment_type=j.get("employment_type", ""),
            source=j.get("source", ""),
            apply_url=j.get("apply_url", ""),
            remote=bool(j.get("remote", False)),
            query=query[:200],
            posted_at=j.get("posted_at", "")[:100],
            first_seen=now,
            last_seen=now,
        ))
        inserted += 1

    db.commit()
    return (inserted, updated)


def count_stored(db: Session) -> int:
    return db.query(func.count(CrawledJob.id)).scalar() or 0


def pool_stats(db: Session) -> dict:
    """Total + a breakdown by country and source for the pool-stats endpoint."""
    total = count_stored(db)
    by_country = dict(
        db.query(CrawledJob.country, func.count(CrawledJob.id)).group_by(CrawledJob.country).all()
    )
    by_source = dict(
        db.query(CrawledJob.source, func.count(CrawledJob.id)).group_by(CrawledJob.source).all()
    )
    return {"total": total, "by_country": by_country, "by_source": by_source}


def query_stored(
    db: Session,
    *,
    country: str = "",
    employment_type: str = "",
    remote: Optional[bool] = None,
    company: str = "",
    text: str = "",
    limit: int = 1000,
) -> list[dict]:
    """Return stored jobs (newest first) as aggregator-shaped dicts for scoring.

    `limit` here is the candidate pool pulled for scoring — the caller ranks by
    match score and shows only the top slice to the user.
    """
    q = db.query(CrawledJob)
    if country:
        q = q.filter(CrawledJob.country == country)
    if employment_type:
        q = q.filter(CrawledJob.employment_type == employment_type)
    if remote is not None:
        q = q.filter(CrawledJob.remote == remote)
    if company:
        q = q.filter(CrawledJob.company.ilike(f"%{company}%"))
    if text:
        like = f"%{text}%"
        q = q.filter((CrawledJob.title.ilike(like)) | (CrawledJob.description.ilike(like)))
    rows = q.order_by(CrawledJob.first_seen.desc()).limit(limit).all()
    return [
        {
            "fingerprint": r.url_hash[:32],
            "source": r.source,
            "title": r.title,
            "company": r.company,
            "location": r.location,
            "salary": r.salary,
            "salary_inr": "",
            "employment_type": r.employment_type,
            "apply_url": r.apply_url,
            "remote": r.remote,
            "posted_at": r.posted_at,
            "description_snippet": r.description,
            "country": r.country,
        }
        for r in rows
    ]
