"""Jobicy Public API — official, public, no key required.

  https://jobicy.com/api/v2/remote-jobs?count=50
Real remote postings with genuine apply URLs and a `jobGeo` field (e.g.
"India", "Anywhere", "USA"), so India-eligible remote roles surface alongside
global ones. Remote-first → coverage for India and other countries.
"""
from __future__ import annotations

import os
from typing import List

from ..base import Provider, RawJob

ENDPOINT = "https://jobicy.com/api/v2/remote-jobs"
COUNT = int(os.getenv("JOBICY_COUNT", "50"))


class JobicyProvider(Provider):
    name = "Jobicy"
    query_agnostic = True
    requires_key = False
    official_api = True

    async def fetch(self, client, query: str, location: str, limit: int) -> List[RawJob]:
        try:
            r = await client.get(ENDPOINT, params={"count": min(COUNT, 100)})
            r.raise_for_status()
            jobs = r.json().get("jobs", []) or []
        except Exception:
            return []
        out: List[RawJob] = []
        for j in jobs:
            url = j.get("url", "")
            if not (j.get("jobTitle") and url):
                continue
            jt = j.get("jobType")
            job_type = ", ".join(jt) if isinstance(jt, list) else (jt or "")
            out.append(RawJob(
                source=self.name,
                title=j.get("jobTitle", ""),
                company=j.get("companyName", "") or "",
                apply_url=url,
                location=j.get("jobGeo", "") or "Remote",
                salary=(f"{j.get('annualSalaryMin'):,} - {j.get('annualSalaryMax'):,} "
                        f"{j.get('salaryCurrency') or 'USD'}"
                        if j.get("annualSalaryMin") and j.get("annualSalaryMax") else ""),
                remote=True,
                posted_at=(j.get("pubDate") or "")[:10],
                job_type=job_type,
                employment_type="internship" if "intern" in j.get("jobTitle", "").lower() else "",
                description_snippet=(j.get("jobExcerpt") or "")[:400],
                external_id=f"jobicy-{j.get('id')}",
                company_domain="jobicy.com",
            ))
        return out
