"""JSearch (RapidAPI) — Google-for-Jobs aggregator. OFFICIAL API only, no scraping.

A free RapidAPI key is required: set `JSEARCH_API_KEY` (optionally `JSEARCH_HOST`,
`JSEARCH_COUNTRY`, `JSEARCH_DEFAULT_QUERY`). JSearch surfaces Google-for-Jobs
listings, giving broad **India + remote + internship/entry-level** coverage that
the no-key providers lack.

Gated like the other keyed providers: `available()` is False until the key is
set, so it returns nothing (and shows a "Source Pending" badge) until configured.
"""
from __future__ import annotations

import os
from typing import List

from ..base import Provider, RawJob

ENDPOINT = "https://jsearch.p.rapidapi.com/search"


class JSearchProvider(Provider):
    name = "JSearch"
    requires_key = True
    official_api = True
    # Query-dependent (JSearch filters upstream by the query string), so the
    # aggregator caches per query — NOT query_agnostic.

    def __init__(self):
        self.key = os.getenv("JSEARCH_API_KEY", "")
        self.host = os.getenv("JSEARCH_HOST", "jsearch.p.rapidapi.com")
        self.country = os.getenv("JSEARCH_COUNTRY", "in")  # India-first default
        # India-first, priority-domain default when the user gives no query.
        self.default_query = os.getenv("JSEARCH_DEFAULT_QUERY", "") or \
            "software engineer OR data scientist OR AI ML intern fresher"
        # Anchor location-less searches to India.
        self.default_location = os.getenv("JSEARCH_DEFAULT_LOCATION", "India")

    def available(self) -> bool:
        return bool(self.key)

    @staticmethod
    def _employment_type(j: dict) -> str:
        # Map JSearch's type to ours; title inference handles fresher vs job.
        if "INTERN" in (j.get("job_employment_type") or "").upper():
            return "internship"
        return ""

    @staticmethod
    def _salary(j: dict) -> str:
        lo, hi = j.get("job_min_salary"), j.get("job_max_salary")
        cur = j.get("job_salary_currency") or ""
        per = (j.get("job_salary_period") or "").lower()
        if lo and hi:
            base = f"{int(lo):,} - {int(hi):,} {cur}".strip()
            return f"{base} / {per}" if per else base
        return ""

    @staticmethod
    def _location(j: dict) -> str:
        parts = [j.get("job_city"), j.get("job_state"), j.get("job_country")]
        return ", ".join(p for p in parts if p) or (j.get("job_country") or "")

    async def fetch(self, client, query: str, location: str, limit: int) -> List[RawJob]:
        q = (query or self.default_query).strip()
        # India-first: anchor location-less searches to India (overridable).
        loc = (location or self.default_location or "").strip()
        # JSearch takes a single free-text query; fold the location in for geo
        # relevance. (Internships/entry-level/remote are kept — not filtered out
        # here — so Jobora's eligibility + internship filter can rank them.)
        full = f"{q} in {loc}" if loc else q
        params = {"query": full, "page": "1", "num_pages": "1", "date_posted": "month",
                  "country": self.country}
        headers = {"X-RapidAPI-Key": self.key, "X-RapidAPI-Host": self.host}
        try:
            r = await client.get(ENDPOINT, params=params, headers=headers)
            r.raise_for_status()
            data = r.json().get("data", []) or []
        except Exception:
            return []  # isolate: a failing provider yields nothing

        out: List[RawJob] = []
        for j in data[:limit]:
            apply_url = j.get("job_apply_link") or j.get("job_google_link") or ""
            if not apply_url:
                continue
            out.append(RawJob(
                source=self.name,
                title=j.get("job_title", "") or "",
                company=j.get("employer_name", "") or "",
                apply_url=apply_url,
                location=self._location(j),
                salary=self._salary(j),
                remote=bool(j.get("job_is_remote")),
                posted_at=(j.get("job_posted_at_datetime_utc") or "")[:10],
                job_type=(j.get("job_employment_type") or "").title(),
                employment_type=self._employment_type(j),
                description_snippet=(j.get("job_description") or "")[:400],
                external_id=f"jsearch-{j.get('job_id', '')}",
                company_domain="",  # apply links vary → generic adapter (Track & Apply)
            ))
        return out
