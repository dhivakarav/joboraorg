"""Ashby provider — discovery via the official public Posting API.

  https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true
This is Ashby's documented, public job-board API (the same data their hosted
boards render), so apply URLs are the genuine application pages. No key required.
"""
from __future__ import annotations

import asyncio
import os
from typing import List

from ..base import Provider, RawJob

# Curated boards with active Ashby job boards. Extend via ASHBY_BOARDS env.
DEFAULT_BOARDS = ["Ramp", "Notion", "Linear", "Vanta", "Posthog", "Mercury"]
ENDPOINT = "https://api.ashbyhq.com/posting-api/job-board/{board}"


class AshbyProvider(Provider):
    name = "Ashby"
    query_agnostic = True  # fetch ignores the query -> cache once, reuse for all queries
    requires_key = False

    def __init__(self):
        env = os.getenv("ASHBY_BOARDS", "")
        self.boards = [b.strip() for b in env.split(",") if b.strip()] or DEFAULT_BOARDS

    @staticmethod
    def _employment_type(j: dict) -> str:
        t = (j.get("employmentType") or "").lower()
        if "intern" in t:
            return "internship"
        return ""  # let title inference classify fresher vs job

    async def _fetch_board(self, client, board: str) -> List[RawJob]:
        try:
            r = await client.get(ENDPOINT.format(board=board),
                                 params={"includeCompensation": "true"})
            r.raise_for_status()
            jobs = r.json().get("jobs", [])
        except Exception:
            return []
        out: List[RawJob] = []
        for j in jobs:
            comp = (j.get("compensation") or {})
            salary = (comp.get("scrapeableCompensationSalarySummary")
                      or comp.get("compensationTierSummary") or "")
            loc = j.get("location") or ""
            out.append(RawJob(
                source=self.name,
                title=j.get("title", ""),
                company=board.replace("-", " ").title(),
                apply_url=j.get("applyUrl") or j.get("jobUrl") or "",
                location=loc,
                salary=salary,
                remote=bool(j.get("isRemote")),
                posted_at=(j.get("publishedAt") or "")[:10],
                job_type=j.get("department", "") or "",
                employment_type=self._employment_type(j),
                description_snippet=j.get("descriptionPlain", "") or "",
                external_id=f"ashby-{board}-{j.get('id')}",
                company_domain="ashbyhq.com",
            ))
        return out

    async def fetch(self, client, query: str, location: str, limit: int) -> List[RawJob]:
        results = await asyncio.gather(
            *[self._fetch_board(client, b) for b in self.boards],
            return_exceptions=True,
        )
        out: List[RawJob] = []
        for res in results:
            if isinstance(res, list):
                out.extend(res)
        return out
