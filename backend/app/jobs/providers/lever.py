"""Lever Postings API — official, public, real openings from real companies.

  https://api.lever.co/v0/postings/{company}?mode=json
No key required. Apply URLs (hostedUrl/applyUrl) are the genuine applications.
"""
from __future__ import annotations

import asyncio
from typing import List

from ..base import Provider, RawJob

DEFAULT_COMPANIES = [
    "voodoo", "ro", "leadiq", "match", "spotify", "brex", "ramp", "notion",
    # India-hiring companies (verified live). Extend via LEVER_COMPANIES.
    "meesho", "zeta", "cred", "paytm", "hevodata", "mindtickle",
]
ENDPOINT = "https://api.lever.co/v0/postings/{company}"


class LeverProvider(Provider):
    name = "Lever"
    query_agnostic = True  # fetch ignores the query -> cache once, reuse for all queries
    requires_key = False

    def __init__(self):
        import os
        env = os.getenv("LEVER_COMPANIES", "")
        self.companies = [c.strip() for c in env.split(",") if c.strip()] or DEFAULT_COMPANIES

    async def _fetch_company(self, client, company: str) -> List[RawJob]:
        try:
            r = await client.get(ENDPOINT.format(company=company), params={"mode": "json"})
            r.raise_for_status()
        except Exception:
            return []
        out: List[RawJob] = []
        for j in r.json():
            cats = j.get("categories", {}) or {}
            loc = cats.get("location", "") or ""
            out.append(RawJob(
                source=self.name,
                title=j.get("text", ""),
                company=company.replace("-", " ").title(),
                apply_url=j.get("hostedUrl") or j.get("applyUrl") or "",
                location=loc,
                remote="remote" in loc.lower() or cats.get("commitment", "").lower() == "remote",
                job_type=cats.get("commitment", "") or "",
                posted_at="",
                description_snippet=j.get("descriptionPlain", "")[:280] if j.get("descriptionPlain") else "",
                external_id=f"lever-{company}-{j.get('id')}",
                company_domain="lever.co",
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
