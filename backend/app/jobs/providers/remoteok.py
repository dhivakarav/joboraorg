"""RemoteOK Public API — official, public, no key required.

  https://remoteok.com/api
Returns a JSON array (first element is a legal/metadata notice) of real remote
postings with genuine apply URLs. Remote-first, global → adds remote coverage
for India and every other country.
"""
from __future__ import annotations

from typing import List

from ..base import Provider, RawJob

ENDPOINT = "https://remoteok.com/api"


class RemoteOKProvider(Provider):
    name = "RemoteOK"
    query_agnostic = True   # one global remote feed; relevance filtered downstream
    requires_key = False
    official_api = True

    async def fetch(self, client, query: str, location: str, limit: int) -> List[RawJob]:
        try:
            r = await client.get(ENDPOINT, headers={"Accept": "application/json"})
            r.raise_for_status()
            data = r.json()
        except Exception:
            return []
        out: List[RawJob] = []
        for j in data:
            if not isinstance(j, dict) or not j.get("position"):
                continue   # skip the leading legal/metadata element
            url = j.get("apply_url") or j.get("url") or ""
            if not url:
                continue
            tags = j.get("tags") or []
            out.append(RawJob(
                source=self.name,
                title=j.get("position", ""),
                company=j.get("company", "") or "",
                apply_url=url,
                location=j.get("location", "") or "Remote",
                salary=(f"{j.get('salary_min'):,} - {j.get('salary_max'):,} USD"
                        if j.get("salary_min") and j.get("salary_max") else ""),
                remote=True,
                posted_at=(j.get("date") or "")[:10],
                job_type=", ".join(tags[:4]) if isinstance(tags, list) else "",
                employment_type="internship" if "intern" in j.get("position", "").lower() else "",
                description_snippet=(j.get("description") or "")[:400],
                external_id=f"remoteok-{j.get('id') or j.get('slug')}",
                company_domain="remoteok.com",
            ))
        return out
