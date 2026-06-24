"""Internshala provider (Phase 1 — discovery only, NO auto-submission).

⚠️ Important legal/technical reality (verified against internshala.com/robots.txt):
Internshala has **no official public jobs API**, and its `robots.txt` **disallows**
the discovery paths we'd need — `/internship/search/`, `/job/search/`,
`/internship/details/`, `/job/details/`, `/api/`, and any `?query` URL. Scraping
those would violate robots.txt and likely the Terms of Service, so Jobara does
**not** do it, and it does **not** fabricate Internshala listings.

This provider is therefore a **lawful integration seam**: it activates only when
the operator supplies an **authorized data source** via `INTERNSHALA_FEED_URL`
(an official API, affiliate/partner feed, or a licensed dataset). Every fetch is
additionally `robots.txt`-gated. With no authorized source configured, it reports
`available() == False` and returns nothing — by design.

When an authorized JSON feed is configured, each record is normalised into the
standard `RawJob` (so match scoring, INR stipend conversion, dedupe, and activity
tracking all work) with `employment_type` set to internship/fresher/job.
"""
from __future__ import annotations

import os
import re
from typing import List
from urllib.parse import urlparse

from .. import india
from ..base import Provider, RawJob
from ..robots import can_fetch

# Operator-supplied AUTHORIZED feed (official API / partner / licensed dataset).
# Expected JSON: a list of records, or {"internships": [...]}. Field mapping below.
FEED_URL = os.getenv("INTERNSHALA_FEED_URL", "")
# If the feed is an authorized API, robots.txt of internshala.com does not apply
# to it; this flag lets an operator skip the robots gate for a non-internshala
# host they're licensed to use. Defaults to enforcing the gate.
SKIP_ROBOTS = os.getenv("INTERNSHALA_FEED_TRUSTED", "0") == "1"
# Operator ASSERTS this feed is a genuine licensed/official/partner source (not
# the local dev mock). Only an authorized feed unlocks real Internshala discovery
# + apply in the UI; otherwise the provider is treated as Mock Mode.
FEED_AUTHORIZED = os.getenv("INTERNSHALA_FEED_AUTHORIZED", "0") == "1"

# Hosts we consider to be the local development MOCK (never a real source).
_MOCK_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0", "::1")

# Set once a real authorized feed has returned at least one record this process
# (distinguishes "Authorized Feed Available" from "Connected").
_LAST_FETCH_OK = False


class InternshalaProvider(Provider):
    name = "Internshala"
    requires_key = True          # needs an authorized feed/source to function
    official_api = False         # not an official Internshala API

    def available(self) -> bool:
        return bool(FEED_URL)

    @staticmethod
    def _is_mock_feed() -> bool:
        if not FEED_URL:
            return False
        host = (urlparse(FEED_URL).netloc.split(":")[0] or "").lower()
        return host in _MOCK_HOSTS or "mock" in FEED_URL.lower()

    def authorized(self) -> bool:
        """True only for a genuine licensed/official feed (not disabled, not mock)."""
        return bool(FEED_URL) and FEED_AUTHORIZED and not self._is_mock_feed()

    def status(self) -> str:
        """One of: Disabled | Mock Mode | Authorized Feed Available | Connected."""
        if not FEED_URL:
            return "Disabled"
        if not self.authorized():
            return "Mock Mode"
        return "Connected" if _LAST_FETCH_OK else "Authorized Feed Available"

    def status_message(self) -> str:
        # The honest "what it does instead" line: even with no direct feed, real
        # Internshala listings still surface when a licensed aggregator (JSearch)
        # returns one whose apply_url points to internshala.com — no fake links.
        _via_aggregator = (" Real Internshala listings still appear when a licensed "
                           "aggregator (JSearch) returns one — never as a fabricated link.")
        return {
            "Disabled": ("Internshala discovery is off — no data source configured. "
                         "Internshala has no public API and its robots.txt disallows "
                         "search/detail scraping." + _via_aggregator),
            "Mock Mode": ("Internshala is running on a LOCAL MOCK feed (sample data, not "
                          "real listings) — this sample data is NEVER shown in real search "
                          "results." + _via_aggregator),
            "Authorized Feed Available": ("An authorized Internshala feed is configured; "
                                          "awaiting the first successful fetch."),
            "Connected": "Connected to an authorized Internshala feed.",
        }[self.status()]

    def unavailable_reason(self) -> str:
        if not FEED_URL:
            return ("No authorized Internshala data source configured. Internshala has "
                    "no public API and its robots.txt disallows search/detail scraping, "
                    "so discovery is disabled until INTERNSHALA_FEED_URL (an official/"
                    "licensed feed) is set.")
        return ""

    @staticmethod
    def _employment_type(rec: dict) -> str:
        t = (rec.get("type") or rec.get("employment_type") or "").lower()
        if "intern" in t:
            return "internship"
        if "fresher" in t or "entry" in t:
            return "fresher"
        return "job"

    @staticmethod
    def _skills(rec: dict) -> List[str]:
        s = rec.get("skills") or rec.get("skills_required") or rec.get("skill") or []
        if isinstance(s, str):
            s = [x.strip() for x in re.split(r"[,;|]", s) if x.strip()]
        return [str(x).strip() for x in s if str(x).strip()]

    def _to_rawjob(self, rec: dict) -> RawJob:
        stipend = str(rec.get("stipend") or rec.get("salary") or "")
        loc_raw = rec.get("location", "") or ""
        is_remote = (bool(rec.get("remote")) or "work from home" in loc_raw.lower()
                     or "remote" in loc_raw.lower())
        # Internshala is an India-only platform → guarantee India tagging so the
        # India-first tier function classifies every record Tier 1 (on-site) or
        # Tier 2 (work-from-home), never global. (Same pattern as the Adzuna fix.)
        if is_remote and not india._is_india(loc_raw):
            loc = "Remote, India"
        elif not india._is_india(loc_raw):
            loc = f"{loc_raw}, India" if loc_raw else "India"
        else:
            loc = loc_raw
        # Store skills as metadata in the snippet (matchable by the resume engine).
        skills = self._skills(rec)
        desc = rec.get("description", "") or ""
        if skills:
            desc = f"Skills: {', '.join(skills)}. {desc}".strip()
        return RawJob(
            source=self.name,
            title=rec.get("title", ""),
            company=rec.get("company", "") or rec.get("company_name", ""),
            apply_url=rec.get("apply_url", "") or rec.get("url", ""),
            location=loc,
            salary=stipend,                      # stipend → salary (INR-converted downstream)
            posted_at=(rec.get("posted_at") or "")[:10],
            deadline=(rec.get("deadline") or "")[:10],
            remote=is_remote,
            job_type=rec.get("category", "") or "",
            employment_type=self._employment_type(rec),
            duration=rec.get("duration", "") or "",
            description_snippet=desc,
            external_id=f"internshala-{rec.get('id')}" if rec.get("id") else "",
            company_domain="internshala.com",
        )

    async def fetch(self, client, query: str, location: str, limit: int) -> List[RawJob]:
        if not FEED_URL:
            return []                                  # disabled — no authorized source
        # Defense-in-depth: NEVER fetch internshala.com HTML directly (robots
        # disallows it). A real licensed feed lives on a partner host, or on an
        # internshala endpoint the operator explicitly trusts
        # (INTERNSHALA_FEED_TRUSTED=1). Otherwise refuse. The robots gate now
        # fails CLOSED (see app/jobs/robots.py), so it is a real second line.
        host = urlparse(FEED_URL).netloc.lower()
        if (host == "internshala.com" or host.endswith(".internshala.com")) and not SKIP_ROBOTS:
            return []
        if not SKIP_ROBOTS and not can_fetch(FEED_URL):
            return []                                  # robots.txt gate (non-internshala host)
        try:
            r = await client.get(FEED_URL, params={"q": query, "location": location} if query else None)
            r.raise_for_status()
            data = r.json()
        except Exception:
            return []
        records = data.get("internships", data) if isinstance(data, dict) else data
        out: List[RawJob] = []
        for rec in (records or [])[:limit * 2]:
            try:
                job = self._to_rawjob(rec)
                if job.is_valid():
                    out.append(job)
            except Exception:
                continue
        # Mark "Connected" once a genuine authorized feed has yielded records.
        if out and self.authorized():
            global _LAST_FETCH_OK
            _LAST_FETCH_OK = True
        return out
