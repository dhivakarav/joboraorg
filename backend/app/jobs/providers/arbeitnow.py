"""Arbeitnow — free public job-board API of real listings. No key required.

Docs: https://www.arbeitnow.com/api
"""
from __future__ import annotations

from typing import List

from ..base import Provider, RawJob

ENDPOINT = "https://www.arbeitnow.com/api/job-board-api"


class ArbeitnowProvider(Provider):
    name = "Arbeitnow"
    query_agnostic = True  # fetch ignores the query -> cache once, reuse for all queries
    requires_key = False

    async def fetch(self, client, query: str, location: str, limit: int) -> List[RawJob]:
        r = await client.get(ENDPOINT)
        r.raise_for_status()
        data = r.json()
        jobs: List[RawJob] = []
        for j in data.get("data", []):
            tags = j.get("job_types", []) or []
            jobs.append(RawJob(
                source=self.name,
                title=j.get("title", ""),
                company=j.get("company_name", ""),
                apply_url=j.get("url", ""),
                location=j.get("location", "") or "",
                remote=bool(j.get("remote")),
                job_type=", ".join(tags),
                posted_at=_iso(j.get("created_at")),
                description_snippet=j.get("description", "") or "",
                external_id=f"arbeitnow-{j.get('slug')}",
                company_domain="arbeitnow.com",
            ))
        return jobs


def _iso(ts):
    if not ts:
        return ""
    try:
        from datetime import datetime, timezone
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).date().isoformat()
    except Exception:
        return ""
