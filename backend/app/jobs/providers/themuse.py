"""The Muse Public Jobs API — official, public, no key required.

  https://www.themuse.com/api/public/jobs?page=N&location=India
Returns real postings from real companies with a genuine landing page. The Muse
supports a `location` filter, so it adds India coverage as well as global roles.
Unauthenticated use is rate-limited (≈500/hr); set THEMUSE_API_KEY to raise it.
"""
from __future__ import annotations

import os
from typing import List

from ..base import Provider, RawJob

ENDPOINT = "https://www.themuse.com/api/public/jobs"
# Locations fetched when the search gives none (India-first + remote).
DEFAULT_LOCATIONS = [l.strip() for l in os.getenv(
    "THEMUSE_LOCATIONS", "India,Flexible / Remote").split(",") if l.strip()]
PAGES = int(os.getenv("THEMUSE_PAGES", "2"))   # pages per location (20 jobs/page)


class TheMuseProvider(Provider):
    name = "TheMuse"
    query_agnostic = True   # no free-text query param; we fetch by location + page
    requires_key = False
    official_api = True

    def __init__(self):
        self.key = os.getenv("THEMUSE_API_KEY", "")

    async def _fetch_page(self, client, location: str, page: int) -> List[RawJob]:
        params = {"page": page}
        if location:
            params["location"] = location
        if self.key:
            params["api_key"] = self.key
        try:
            r = await client.get(ENDPOINT, params=params)
            r.raise_for_status()
            results = r.json().get("results", []) or []
        except Exception:
            return []
        out: List[RawJob] = []
        for j in results:
            locs = [l.get("name", "") for l in (j.get("locations") or []) if l.get("name")]
            loc = ", ".join(locs)
            url = (j.get("refs") or {}).get("landing_page", "")
            if not (j.get("name") and url):
                continue
            out.append(RawJob(
                source=self.name,
                title=j.get("name", ""),
                company=(j.get("company") or {}).get("name", "") or "",
                apply_url=url,
                location=loc,
                remote=any("remote" in l.lower() or "flexible" in l.lower() for l in locs),
                posted_at=(j.get("publication_date") or "")[:10],
                job_type=", ".join(c.get("name", "") for c in (j.get("categories") or [])),
                employment_type="internship" if "intern" in j.get("name", "").lower() else "",
                external_id=f"themuse-{j.get('id')}",
                company_domain="themuse.com",
            ))
        return out

    async def fetch(self, client, query: str, location: str, limit: int) -> List[RawJob]:
        locs = [location] if location else DEFAULT_LOCATIONS
        out: List[RawJob] = []
        for loc in locs:
            for page in range(1, PAGES + 1):
                out.extend(await self._fetch_page(client, loc, page))
                if len(out) >= limit * 2:
                    return out
        return out
