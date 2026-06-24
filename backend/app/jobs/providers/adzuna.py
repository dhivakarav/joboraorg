"""Adzuna Jobs API — real aggregated listings across many countries.

Free developer key required (app_id + app_key) from https://developer.adzuna.com.
Set ADZUNA_APP_ID and ADZUNA_APP_KEY to enable. Gives genuine India ('in') and
Singapore ('sg') coverage, which the no-key providers lack.
"""
from __future__ import annotations

import asyncio
import os
import re
from typing import List

from .. import india
from ..base import Provider, RawJob, infer_employment_type

# Map our market labels to Adzuna country codes (UAE is not supported by Adzuna).
COUNTRY_BY_LOCATION = {
    "india": "in", "singapore": "sg",
}
# {page} is the 1-based page index — Adzuna paginates via the path, not a param.
ENDPOINT = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"

# Adzuna free tier allows up to 50 results/page. We loop pages until the API runs
# out (or the per-search page cap) so the user gets the MAX real volume the free
# tier provides — bounded by ADZUNA_MAX_PAGES so a single search never hammers the
# quota (250 calls/day on the free plan). Each page = 1 API call per country.
RESULTS_PER_PAGE = 50
MAX_PAGES = int(os.getenv("ADZUNA_MAX_PAGES", "5"))      # 5 pages × 50 = 250/country
# Small pause between page calls so we stay well under Adzuna's per-minute limit.
PAGE_PAUSE_SEC = float(os.getenv("ADZUNA_PAGE_PAUSE", "0.25"))

# Adzuna has no explicit remote flag — infer it from the text.
_REMOTE_RE = re.compile(r"\bremote\b|work from home|\bwfh\b|hybrid", re.I)


class AdzunaProvider(Provider):
    name = "Adzuna"
    requires_key = True
    supports_recent = True   # fetch() accepts recent= to sort newest-first (Refresh)

    def __init__(self):
        self.app_id = os.getenv("ADZUNA_APP_ID", "")
        self.app_key = os.getenv("ADZUNA_APP_KEY", "")

    def available(self) -> bool:
        return bool(self.app_id and self.app_key)

    async def _fetch_country(self, client, country: str, query: str, limit: int,
                             recent_first: bool = False) -> List[RawJob]:
        """Pull as many pages as the free tier allows, until Adzuna returns a short
        (last) page or we hit the per-search page cap or the caller's limit."""
        out: List[RawJob] = []
        # How many pages we actually need to satisfy `limit` (still bounded by MAX_PAGES).
        pages_needed = max(1, min(MAX_PAGES, (limit + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE))
        for page in range(1, pages_needed + 1):
            params = {
                "app_id": self.app_id,
                "app_key": self.app_key,
                "results_per_page": RESULTS_PER_PAGE,
                "content-type": "application/json",
            }
            if query:
                params["what"] = query
            if recent_first:
                params["sort_by"] = "date"   # Refresh wants the newest postings first
            try:
                r = await client.get(ENDPOINT.format(country=country, page=page), params=params)
                r.raise_for_status()
                results = r.json().get("results", [])
            except Exception:
                break   # stop paginating this country on error; keep what we have
            out.extend(self._parse_results(results, country))
            if len(results) < RESULTS_PER_PAGE:
                break   # last page reached — Adzuna has nothing more
            if len(out) >= limit:
                break
            await asyncio.sleep(PAGE_PAUSE_SEC)
        return out

    def _parse_results(self, results: list, country: str) -> List[RawJob]:
        out: List[RawJob] = []
        for j in results:
            title = j.get("title", "") or ""
            desc = j.get("description", "") or ""
            loc = (j.get("location") or {}).get("display_name", "") or ""
            smin, smax = j.get("salary_min"), j.get("salary_max")
            salary = ""
            if smin and smax:
                # Adzuna 'in' salaries are already INR; label them so INR display is correct.
                cur = j.get("salary_currency", "") or ("INR" if country == "in" else "")
                salary = f"{int(smin):,} - {int(smax):,} {cur}".strip()
            # Remote inference (Adzuna has no explicit flag).
            remote = bool(_REMOTE_RE.search(f"{title} {loc} {desc}"))
            # India guarantee: a country=in result IS India even when Adzuna labels it
            # with a region/state only ("Karnataka") or a bare city — tag it so the
            # India-first tier function (india_tier) classifies it Tier 1/2, not global.
            if country == "in" and not india._is_india(loc):
                loc = f"{loc}, India" if loc else "India"
            out.append(RawJob(
                source=self.name,
                title=title,
                company=(j.get("company") or {}).get("display_name", "") or "",
                apply_url=j.get("redirect_url", ""),
                location=loc or country.upper(),
                salary=salary,
                remote=remote,
                posted_at=(j.get("created") or "")[:10],
                job_type=j.get("contract_time", "") or "",
                employment_type=infer_employment_type(title, ""),
                description_snippet=desc,
                external_id=f"adzuna-{j.get('id')}",
                company_domain="adzuna",
            ))
        return out

    async def fetch(self, client, query: str, location: str, limit: int,
                    recent: bool = False) -> List[RawJob]:
        # Map the requested location to an Adzuna country. If a SPECIFIC location
        # was given that Adzuna doesn't cover (e.g. Dubai/UAE — Adzuna has no UAE
        # country), return nothing rather than silently serving India/Singapore
        # jobs as if they were that location. Only when NO location is given do we
        # default to the India-first set (in + sg).
        loc = (location or "").lower()
        mapped = [c for name, c in COUNTRY_BY_LOCATION.items() if name in loc]
        if loc and not mapped:
            return []   # location specified but unsupported by Adzuna
        countries = mapped or ["in", "sg"]
        results = await asyncio.gather(
            *[self._fetch_country(client, c, query, limit, recent_first=recent)
              for c in set(countries)],
            return_exceptions=True,
        )
        jobs: List[RawJob] = []
        for res in results:
            if isinstance(res, list):
                jobs.extend(res)
        return jobs
