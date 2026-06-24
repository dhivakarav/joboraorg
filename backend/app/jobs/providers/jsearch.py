"""JSearch (RapidAPI) — Google-for-Jobs aggregator. OFFICIAL API only, no scraping.

A free RapidAPI key is required: set `JSEARCH_API_KEY` (optionally `JSEARCH_HOST`,
`JSEARCH_COUNTRY`, `JSEARCH_DEFAULT_QUERY`). JSearch surfaces Google-for-Jobs
listings, giving broad **India + remote + internship/entry-level** coverage that
the no-key providers lack.

Gated like the other keyed providers: `available()` is False until the key is
set, so it returns nothing (and shows a "Source Pending" badge) until configured.
"""
from __future__ import annotations

import os
from typing import List

from ..base import Provider, RawJob

ENDPOINT = "https://jsearch.p.rapidapi.com/search"

# JSearch returns ~10 results/page. Two hard realities shape the default:
#   1. QUOTA: on the free tier each *page* counts against the monthly request quota
#      (200 requests/month) — num_pages=N spends N requests.
#   2. LATENCY: each page adds ~5-6s to the round-trip. num_pages=2 (~12s) is too
#      slow to reliably finish inside the search deadline; num_pages=1 (~6s) does.
# So the default is 1 page: fast, quota-light (200 searches/month), and reliable.
# Adzuna — not JSearch — is the India volume driver; JSearch's unique value is Dubai
# (no Adzuna UAE country). Raise JSEARCH_NUM_PAGES for deeper NORMAL searches; a
# REFRESH always uses a single page to stay within the live wall-clock deadline.
NUM_PAGES = max(1, int(os.getenv("JSEARCH_NUM_PAGES", "1")))


class JSearchProvider(Provider):
    name = "JSearch"
    requires_key = True
    official_api = True
    supports_recent = True   # fetch() accepts recent= to bias toward newest postings
    # Query-dependent (JSearch filters upstream by the query string), so the
    # aggregator caches per query — NOT query_agnostic.

    def __init__(self):
        self.key = os.getenv("JSEARCH_API_KEY", "")
        self.host = os.getenv("JSEARCH_HOST", "jsearch.p.rapidapi.com")
        self.country = os.getenv("JSEARCH_COUNTRY", "in")  # India-first default
        # India-first, priority-domain default when the user gives no query.
        self.default_query = os.getenv("JSEARCH_DEFAULT_QUERY", "") or \
            "software engineer OR data scientist OR AI ML intern fresher"
        # Anchor location-less searches to India.
        self.default_location = os.getenv("JSEARCH_DEFAULT_LOCATION", "India")
        # Track the last fetch so status() can report "Needs Configuration" when a
        # key is set but the endpoint yields nothing (e.g. pointed at a dev mock).
        self._fetched = False
        self._last_count = 0
        self._rate_limited = False        # True after a 429 (monthly quota exhausted)
        self._quota_remaining = None      # last seen x-ratelimit-requests-remaining

    def available(self) -> bool:
        return bool(self.key)

    def _is_rapidapi(self) -> bool:
        return "rapidapi.com" in (self.host or "").lower()

    def status(self) -> str:
        """Connected only when a key is set, the host is the real RapidAPI host,
        and (once fetched) it actually returns jobs. Distinguishes a real rate-limit
        (free monthly quota used up) from a genuine misconfiguration."""
        if not self.key:
            return "Disabled"
        if not self._is_rapidapi():
            return "Needs Configuration"        # non-RapidAPI host (mock/dev)
        if self._rate_limited:
            return "Rate Limited"               # 429 — free monthly quota exhausted
        if self._fetched and self._last_count == 0:
            return "Needs Configuration"        # key+host set but returns nothing
        return "Connected"

    def status_message(self) -> str:
        s = self.status()
        if s == "Rate Limited":
            rem = self._quota_remaining
            return ("JSearch free-tier monthly request quota is exhausted (HTTP 429)"
                    + (f"; {rem} requests remaining" if rem is not None else "")
                    + ". It resumes next cycle or on a paid plan. India volume is "
                    "unaffected — Adzuna + the ATS boards drive India coverage.")
        return {
            "Disabled": "JSearch needs a free RapidAPI key (set JSEARCH_API_KEY).",
            "Needs Configuration": ("JSearch is not correctly configured: set JSEARCH_HOST="
                                    "jsearch.p.rapidapi.com and a valid JSEARCH_API_KEY. It is "
                                    "currently returning no jobs (likely a mock/dev host)."),
            "Connected": "Connected to JSearch (Google-for-Jobs via RapidAPI)."
                         + (f" {self._quota_remaining} free requests left this cycle."
                            if self._quota_remaining is not None else ""),
        }[s]

    @staticmethod
    def _employment_type(j: dict) -> str:
        # Map JSearch's type to ours; title inference handles fresher vs job.
        if "INTERN" in (j.get("job_employment_type") or "").upper():
            return "internship"
        return ""

    @staticmethod
    def _salary(j: dict) -> str:
        lo, hi = j.get("job_min_salary"), j.get("job_max_salary")
        cur = j.get("job_salary_currency") or ""
        per = (j.get("job_salary_period") or "").lower()
        if lo and hi:
            base = f"{int(lo):,} - {int(hi):,} {cur}".strip()
            return f"{base} / {per}" if per else base
        return ""

    @staticmethod
    def _location(j: dict) -> str:
        parts = [j.get("job_city"), j.get("job_state"), j.get("job_country")]
        return ", ".join(p for p in parts if p) or (j.get("job_country") or "")

    async def fetch(self, client, query: str, location: str, limit: int,
                    recent: bool = False) -> List[RawJob]:
        q = (query or self.default_query).strip()
        # India-first: anchor location-less searches to India (overridable).
        loc = (location or self.default_location or "").strip()
        # JSearch takes a single free-text query; fold the location in for geo
        # relevance. (Internships/entry-level/remote are kept — not filtered out
        # here — so Jobora's eligibility + internship filter can rank them.)
        full = f"{q} in {loc}" if loc else q
        # Pull as many pages as configured in ONE request (num_pages) — the quota-
        # efficient way to maximise free-tier volume. Cap by what `limit` needs.
        # On REFRESH, request a single page: JSearch round-trip time scales with
        # num_pages (~6s/page), so 1 page keeps the live refresh comfortably inside
        # the aggregator's wall-clock deadline (and the freshest jobs are on page 1).
        want_pages = 1 if recent else max(1, min(NUM_PAGES, (limit + 9) // 10))
        params = {"query": full, "page": "1", "num_pages": str(want_pages),
                  # Refresh → "today"/"3days" surfaces the freshest postings first.
                  "date_posted": "3days" if recent else "month",
                  "country": self.country}
        headers = {"X-RapidAPI-Key": self.key, "X-RapidAPI-Host": self.host}
        try:
            r = await client.get(ENDPOINT, params=params, headers=headers)
            # Capture the free-tier quota signal for honest status reporting.
            rem = r.headers.get("x-ratelimit-requests-remaining")
            if rem is not None:
                try:
                    self._quota_remaining = int(rem)
                except ValueError:
                    pass
            if r.status_code == 429:
                self._rate_limited = True   # monthly free quota exhausted
                self._fetched = True
                self._last_count = 0
                return []
            self._rate_limited = False
            r.raise_for_status()
            data = r.json().get("data", []) or []
        except Exception:
            self._fetched = True
            self._last_count = 0
            return []  # isolate: a failing provider yields nothing

        out: List[RawJob] = []
        for j in data[:limit]:
            apply_url = j.get("job_apply_link") or j.get("job_google_link") or ""
            if not apply_url:
                continue
            out.append(RawJob(
                source=self.name,
                title=j.get("job_title", "") or "",
                company=j.get("employer_name", "") or "",
                apply_url=apply_url,
                location=self._location(j),
                salary=self._salary(j),
                remote=bool(j.get("job_is_remote")),
                posted_at=(j.get("job_posted_at_datetime_utc") or "")[:10],
                job_type=(j.get("job_employment_type") or "").title(),
                employment_type=self._employment_type(j),
                description_snippet=(j.get("job_description") or "")[:400],
                external_id=f"jsearch-{j.get('job_id', '')}",
                company_domain="",  # apply links vary → generic adapter (Track & Apply)
            ))
        self._fetched = True
        self._last_count = len(out)
        return out
