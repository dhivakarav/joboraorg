"""Jooble API — real aggregated listings with global coverage incl. UAE/Dubai.

Free key required from https://jooble.org/api/about. Set JOOBLE_API_KEY to
enable. Jooble takes a free-text location, so Dubai / Singapore / India all work.
"""
from __future__ import annotations

import os
from typing import List

from ..base import Provider, RawJob

ENDPOINT = "https://jooble.org/api/{key}"


class JoobleProvider(Provider):
    name = "Jooble"
    requires_key = True

    def __init__(self):
        self.key = os.getenv("JOOBLE_API_KEY", "")

    def available(self) -> bool:
        return bool(self.key)

    async def fetch(self, client, query: str, location: str, limit: int) -> List[RawJob]:
        payload = {"keywords": query or "developer", "location": location or ""}
        try:
            r = await client.post(ENDPOINT.format(key=self.key), json=payload)
            r.raise_for_status()
        except Exception:
            return []
        out: List[RawJob] = []
        for j in r.json().get("jobs", [])[:limit]:
            out.append(RawJob(
                source=self.name,
                title=j.get("title", ""),
                company=j.get("company", "") or "",
                apply_url=j.get("link", ""),
                location=j.get("location", "") or "",
                salary=j.get("salary", "") or "",
                job_type=j.get("type", "") or "",
                posted_at=(j.get("updated") or "")[:10],
                description_snippet=j.get("snippet", "") or "",
                external_id=f"jooble-{j.get('id')}",
                company_domain="jooble",
            ))
        return out
