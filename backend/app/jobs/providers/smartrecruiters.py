"""SmartRecruiters Posting API — official, public, real openings. No key required.

Each company exposes its live postings at:
  https://api.smartrecruiters.com/v1/companies/{company}/postings
These are the same postings the company's SmartRecruiters careers site serves, so
the apply URLs (jobs.smartrecruiters.com/{Company}/{id}) are the genuine
application pages. Used here to add India coverage (e.g. Freshworks is India-HQ'd
and posts heavily in Chennai/Bengaluru/Hyderabad).

Extend the company set via the SMARTRECRUITERS_COMPANIES env var (comma-separated
company identifiers).
"""
from __future__ import annotations

import asyncio
import os
from typing import List

from ..base import Provider, RawJob

# Curated companies with active SmartRecruiters boards that hire in India.
DEFAULT_COMPANIES = ["freshworks", "visa", "ixigo"]  # India-hiring (verified live)
ENDPOINT = "https://api.smartrecruiters.com/v1/companies/{company}/postings"
# Public careers URL the posting resolves to (genuine application page).
APPLY_URL = "https://jobs.smartrecruiters.com/{company}/{posting_id}"


class SmartRecruitersProvider(Provider):
    name = "SmartRecruiters"
    query_agnostic = True   # fetch ignores the query -> cache once, reuse for all queries
    requires_key = False
    official_api = True

    def __init__(self):
        env = os.getenv("SMARTRECRUITERS_COMPANIES", "")
        self.companies = [c.strip() for c in env.split(",") if c.strip()] or DEFAULT_COMPANIES

    @staticmethod
    def _location(j: dict) -> str:
        loc = j.get("location") or {}
        full = loc.get("fullLocation")
        if full:
            return ", ".join(p.strip() for p in full.split(",") if p.strip())
        parts = [loc.get("city"), loc.get("region"), loc.get("country")]
        return ", ".join(p for p in parts if p)

    async def _fetch_company(self, client, company: str) -> List[RawJob]:
        try:
            r = await client.get(ENDPOINT.format(company=company), params={"limit": 100})
            r.raise_for_status()
            content = r.json().get("content", []) or []
        except Exception:
            return []
        out: List[RawJob] = []
        for j in content:
            loc = j.get("location") or {}
            ident = (j.get("company") or {}).get("identifier") or company
            pid = j.get("id")
            if not pid:
                continue
            out.append(RawJob(
                source=self.name,
                title=j.get("name", "") or "",
                company=(j.get("company") or {}).get("name") or company.title(),
                apply_url=APPLY_URL.format(company=ident, posting_id=pid),
                location=self._location(j),
                remote=bool(loc.get("remote")),
                posted_at=(j.get("releasedDate") or "")[:10],
                external_id=f"smartrecruiters-{company}-{pid}",
                company_domain="smartrecruiters.com",
            ))
        return out

    async def fetch(self, client, query: str, location: str, limit: int) -> List[RawJob]:
        results = await asyncio.gather(
            *[self._fetch_company(client, c) for c in self.companies],
            return_exceptions=True,
        )
        jobs: List[RawJob] = []
        for res in results:
            if isinstance(res, list):
                jobs.extend(res)
        return jobs
