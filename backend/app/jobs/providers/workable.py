"""Workable provider — discovery via the AUTHORIZED account API.

Workable does **not** expose a free, unauthenticated public jobs API (the public
endpoints return `invalid_token`). Discovery therefore requires the operator's
own Workable **account API token** plus the account subdomain(s):
  GET https://{subdomain}.workable.com/spi/v3/jobs   (Authorization: Bearer <token>)

Without `WORKABLE_TOKEN` + `WORKABLE_SUBDOMAINS`, the provider is disabled and
returns nothing — no scraping, no fabricated data.
"""
from __future__ import annotations

import os
from typing import List

from ..base import Provider, RawJob

TOKEN = os.getenv("WORKABLE_TOKEN", "")
SUBDOMAINS = [s.strip() for s in os.getenv("WORKABLE_SUBDOMAINS", "").split(",") if s.strip()]
ENDPOINT = "https://{sub}.workable.com/spi/v3/jobs"


class WorkableProvider(Provider):
    name = "Workable"
    requires_key = True
    official_api = True

    def available(self) -> bool:
        return bool(TOKEN and SUBDOMAINS)

    def unavailable_reason(self) -> str:
        return ("Workable discovery needs an authorized account token. Set "
                "WORKABLE_TOKEN and WORKABLE_SUBDOMAINS (no public/unauth API exists).")

    async def fetch(self, client, query: str, location: str, limit: int) -> List[RawJob]:
        if not self.available():
            return []
        out: List[RawJob] = []
        headers = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"}
        for sub in SUBDOMAINS:
            try:
                r = await client.get(ENDPOINT.format(sub=sub), headers=headers,
                                     params={"state": "published", "limit": min(limit, 100)})
                r.raise_for_status()
                jobs = r.json().get("jobs", [])
            except Exception:
                continue
            for j in jobs:
                loc = " ".join(filter(None, [(j.get("location") or {}).get("city"),
                                             (j.get("location") or {}).get("country")]))
                out.append(RawJob(
                    source=self.name,
                    title=j.get("title", ""),
                    company=j.get("company", sub) or sub,
                    apply_url=j.get("application_url") or j.get("shortlink") or j.get("url", ""),
                    location=loc,
                    remote=bool((j.get("location") or {}).get("workplace_type") == "remote"
                                or j.get("telecommuting")),
                    posted_at=(j.get("created_at") or "")[:10],
                    job_type=j.get("department", "") or "",
                    employment_type="internship" if "intern" in (j.get("employment_type") or "").lower() else "",
                    description_snippet=j.get("description", "") or "",
                    external_id=f"workable-{sub}-{j.get('shortcode') or j.get('id')}",
                    company_domain="workable.com",
                ))
        return out
