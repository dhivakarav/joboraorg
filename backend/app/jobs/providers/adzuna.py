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
ENDPOINT = "https://api.adzuna.com/v1/api/jobs/{country}/search/1"

# Adzuna has no explicit remote flag — infer it from the text.
_REMOTE_RE = re.compile(r"\bremote\b|work from home|\bwfh\b|hybrid", re.I)


class AdzunaProvider(Provider):
    name = "Adzuna"
    requires_key = True

    def __init__(self):
        self.app_id = os.getenv("ADZUNA_APP_ID", "")
        self.app_key = os.getenv("ADZUNA_APP_KEY", "")

    def available(self) -> bool:
        return bool(self.app_id and self.app_key)

    async def _fetch_country(self, client, country: str, query: str, limit: int) -> List[RawJob]:
        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "results_per_page": min(limit, 50),
            "content-type": "application/json",
        }
        if query:
            params["what"] = query
        try:
            r = await client.get(ENDPOINT.format(country=country), params=params)
            r.raise_for_status()
        except Exception:
            return []
        out: List[RawJob] = []
        for j in r.json().get("results", []):
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

    async def fetch(self, client, query: str, location: str, limit: int) -> List[RawJob]:
        # Pick countries from the requested location, else default to in + sg.
        loc = (location or "").lower()
        countries = [c for name, c in COUNTRY_BY_LOCATION.items() if name in loc] or ["in", "sg"]
        results = await asyncio.gather(
            *[self._fetch_country(client, c, query, limit) for c in set(countries)],
            return_exceptions=True,
        )
        jobs: List[RawJob] = []
        for res in results:
            if isinstance(res, list):
                jobs.extend(res)
        return jobs
