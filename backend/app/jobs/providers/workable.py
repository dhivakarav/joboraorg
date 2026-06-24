"""Workable provider — discovery via the PUBLIC, no-auth job-board widget API.

Workable hosts each company's careers page at apply.workable.com/{account}. The
widget that powers it is backed by a public, token-free endpoint:

    GET https://apply.workable.com/api/v1/widget/accounts/{account}
    → {"name": <company>, "description": ..., "jobs": [ {title, shortcode,
       application_url, city/state/country, telecommuting, published_on, ...}, ...]}

This is the same model as Greenhouse boards: there is NO global Workable search,
so we maintain a curated list of company "account" slugs known to post on
Workable and fetch each concurrently (query-agnostic → cached once, reused for
all queries). Extend the list via the WORKABLE_ACCOUNTS env var (comma-separated
account slugs). No token, no scraping — just the company's own public board API.

Note: the widget list response does NOT include the full job description, so the
resume-match signal is built from the title + department/function/industry.
"""
from __future__ import annotations

import asyncio
import os
from typing import List

from ..base import Provider, RawJob, infer_employment_type

# Curated set of companies with currently-active Workable boards (verified live).
# Extend via the WORKABLE_ACCOUNTS env var (comma-separated account slugs).
DEFAULT_ACCOUNTS = [
    "zego", "kuda", "dext", "oysterhr",
]
ENDPOINT = "https://apply.workable.com/api/v1/widget/accounts/{account}"

# The widget endpoint is browser-facing (Cloudflare-fronted). Identify as a normal
# JSON client so requests aren't served the HTML rate-limit/challenge page meant
# for crawlers. We stay gentle anyway: one request per account, cached for 15 min.
_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"),
    "Accept": "application/json",
}


class WorkableProvider(Provider):
    name = "Workable"
    query_agnostic = True   # fetch ignores the query → cache once, reuse for all queries
    requires_key = False     # public widget API; no token required
    official_api = True

    def __init__(self):
        env = os.getenv("WORKABLE_ACCOUNTS", "")
        self.accounts = [a.strip() for a in env.split(",") if a.strip()] or DEFAULT_ACCOUNTS

    def available(self) -> bool:
        # Public API; usable as long as we have at least one account slug to query.
        return bool(self.accounts)

    def status_message(self) -> str:
        if self.available():
            return (f"Connected to Workable's public board API across "
                    f"{len(self.accounts)} known company account(s). Like Greenhouse, "
                    f"Workable has no global search — coverage is the curated account "
                    f"list (extend via WORKABLE_ACCOUNTS).")
        return "Workable has no company accounts configured (set WORKABLE_ACCOUNTS)."

    async def _fetch_account(self, client, account: str) -> List[RawJob]:
        try:
            r = await client.get(ENDPOINT.format(account=account), headers=_HEADERS)
            r.raise_for_status()
            data = r.json()
        except Exception:
            return []   # Cloudflare 429 / transient error → isolate (cache covers next run)
        company = data.get("name") or account.replace("-", " ").title()
        out: List[RawJob] = []
        for j in data.get("jobs", []) or []:
            apply_url = j.get("application_url") or j.get("shortlink") or j.get("url", "")
            if not apply_url:
                continue
            loc = ", ".join(filter(None, [j.get("city"), j.get("state"), j.get("country")]))
            title = j.get("title", "") or ""
            # No description in the widget payload — synthesise a signal from the
            # structured fields so the resume matcher has more than just the title.
            signal = " ".join(filter(None, [title, j.get("department"), j.get("function"),
                                            j.get("industry")]))
            emp = j.get("employment_type") or ""
            out.append(RawJob(
                source=self.name,
                title=title,
                company=company,
                apply_url=apply_url,
                location=loc,
                remote=bool(j.get("telecommuting")),
                posted_at=(j.get("published_on") or j.get("created_at") or "")[:10],
                job_type=j.get("department", "") or "",
                employment_type=infer_employment_type(title,
                                                      "internship" if "intern" in emp.lower() else ""),
                description_snippet=signal,
                external_id=f"workable-{account}-{j.get('shortcode') or j.get('code')}",
                company_domain="workable.com",
            ))
        return out

    async def fetch(self, client, query: str, location: str, limit: int) -> List[RawJob]:
        if not self.available():
            return []
        results = await asyncio.gather(
            *[self._fetch_account(client, a) for a in self.accounts],
            return_exceptions=True,
        )
        jobs: List[RawJob] = []
        for res in results:
            if isinstance(res, list):
                jobs.extend(res)
        return jobs
