"""Wellfound (AngelList Talent) provider — discovery via an AUTHORIZED source only.

⚠️ Wellfound has **no public jobs API**, and its `robots.txt` disallows the
job-listing paths (`/_jobs/`, `?jobId`, `?jobSlug`, `?role`, `/auth/` …). Its job
data sits behind an authenticated GraphQL endpoint. So lawful discovery is **not**
possible by scraping, and Jobora does not scrape it or fabricate listings.

This provider is a robots-gated seam: it activates only when the operator
configures an **authorized data source** via `WELLFOUND_FEED_URL` (a licensed
dataset / partner feed). Without one it reports unavailable and returns nothing.
"""
from __future__ import annotations

import os
from typing import List

from ..base import Provider, RawJob
from ..robots import can_fetch

FEED_URL = os.getenv("WELLFOUND_FEED_URL", "")
SKIP_ROBOTS = os.getenv("WELLFOUND_FEED_TRUSTED", "0") == "1"


class WellfoundProvider(Provider):
    name = "Wellfound"
    requires_key = True
    official_api = False

    def available(self) -> bool:
        return bool(FEED_URL)

    def unavailable_reason(self) -> str:
        return ("No authorized Wellfound data source configured. Wellfound has no "
                "public API and its robots.txt disallows job paths, so discovery is "
                "disabled until WELLFOUND_FEED_URL (a licensed/partner feed) is set.")

    async def fetch(self, client, query: str, location: str, limit: int) -> List[RawJob]:
        if not FEED_URL:
            return []
        if not SKIP_ROBOTS and not can_fetch(FEED_URL):
            return []
        try:
            r = await client.get(FEED_URL, params={"q": query, "location": location} if query else None)
            r.raise_for_status()
            data = r.json()
        except Exception:
            return []
        records = data.get("jobs", data) if isinstance(data, dict) else data
        out: List[RawJob] = []
        for rec in (records or [])[:limit * 2]:
            try:
                job = RawJob(
                    source=self.name,
                    title=rec.get("title", ""),
                    company=rec.get("company", "") or rec.get("startup", ""),
                    apply_url=rec.get("apply_url", "") or rec.get("url", ""),
                    location=rec.get("location", "") or "",
                    salary=str(rec.get("salary") or rec.get("compensation") or ""),
                    remote=bool(rec.get("remote")),
                    employment_type="internship" if "intern" in (rec.get("type") or "").lower() else "",
                    description_snippet=rec.get("description", "") or "",
                    external_id=f"wellfound-{rec.get('id')}" if rec.get("id") else "",
                    company_domain="wellfound.com",
                )
                if job.is_valid():
                    out.append(job)
            except Exception:
                continue
        return out
