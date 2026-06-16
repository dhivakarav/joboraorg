"""Greenhouse Job Board API — official, public, real openings from real companies.

Each company exposes a board at:
  https://boards-api.greenhouse.io/v1/boards/{board}/jobs
These are the same endpoints the companies' own career pages consume, so the
apply URLs are the genuine application pages. No key required.
"""
from __future__ import annotations

import asyncio
from typing import List

from ..base import Provider, RawJob

# Curated set of companies with currently-active Greenhouse boards. Extend via
# the GREENHOUSE_BOARDS env var (comma-separated board tokens).
DEFAULT_BOARDS = [
    "stripe", "airbnb", "dropbox", "coinbase", "databricks", "gitlab",
    "robinhood", "doordash", "instacart", "figma",
]
ENDPOINT = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs"


class GreenhouseProvider(Provider):
    name = "Greenhouse"
    query_agnostic = True  # fetch ignores the query -> cache once, reuse for all queries
    requires_key = False

    def __init__(self):
        import os
        env = os.getenv("GREENHOUSE_BOARDS", "")
        self.boards = [b.strip() for b in env.split(",") if b.strip()] or DEFAULT_BOARDS

    async def _fetch_board(self, client, board: str) -> List[RawJob]:
        try:
            r = await client.get(ENDPOINT.format(board=board), params={"content": "false"})
            r.raise_for_status()
        except Exception:
            return []
        out: List[RawJob] = []
        for j in r.json().get("jobs", []):
            loc = (j.get("location") or {}).get("name", "")
            out.append(RawJob(
                source=self.name,
                title=j.get("title", ""),
                company=board.replace("-", " ").title(),
                apply_url=j.get("absolute_url", ""),
                location=loc,
                remote="remote" in loc.lower(),
                posted_at=(j.get("updated_at") or "")[:10],
                external_id=f"gh-{board}-{j.get('id')}",
                company_domain="greenhouse.io",
            ))
        return out

    async def fetch(self, client, query: str, location: str, limit: int) -> List[RawJob]:
        results = await asyncio.gather(
            *[self._fetch_board(client, b) for b in self.boards],
            return_exceptions=True,
        )
        jobs: List[RawJob] = []
        for res in results:
            if isinstance(res, list):
                jobs.extend(res)
        return jobs
