"""Remotive — free public API of real remote jobs. No key required.

Docs: https://remotive.com/api/remote-jobs
"""
from __future__ import annotations

from typing import List

from ..base import Provider, RawJob

ENDPOINT = "https://remotive.com/api/remote-jobs"


class RemotiveProvider(Provider):
    name = "Remotive"
    requires_key = False

    async def fetch(self, client, query: str, location: str, limit: int) -> List[RawJob]:
        params = {"limit": min(limit * 3, 100)}
        if query:
            params["search"] = query
        r = await client.get(ENDPOINT, params=params)
        r.raise_for_status()
        data = r.json()
        jobs: List[RawJob] = []
        for j in data.get("jobs", []):
            jobs.append(RawJob(
                source=self.name,
                title=j.get("title", ""),
                company=j.get("company_name", ""),
                apply_url=j.get("url", ""),
                location=j.get("candidate_required_location", "") or "Remote",
                salary=j.get("salary", "") or "",
                posted_at=j.get("publication_date", "") or "",
                remote=True,
                job_type=j.get("job_type", "") or "",
                description_snippet=j.get("description", "") or "",
                external_id=f"remotive-{j.get('id')}",
                company_domain="remotive.com",
            ))
        return jobs
