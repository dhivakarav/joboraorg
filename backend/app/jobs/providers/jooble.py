"""Jooble API — official aggregated listings. India-first, internship + fresher.

Official API only (no scraping): a free key from https://jooble.org/api/about is
required — set JOOBLE_API_KEY to enable. Jooble takes a free-text location, so
India (and any city) works. Jobs are TRACK & APPLY only — Jobora never
auto-submits to Jooble; the user applies on the genuine listing link.
"""
from __future__ import annotations

import os
from typing import List

from ..base import Provider, RawJob, infer_employment_type

ENDPOINT = "https://jooble.org/api/{key}"


class JoobleProvider(Provider):
    name = "Jooble"
    requires_key = True
    official_api = True

    def __init__(self):
        self.key = os.getenv("JOOBLE_API_KEY", "")
        # India-first: anchor location-less searches to India (overridable).
        self.default_location = os.getenv("JOOBLE_DEFAULT_LOCATION", "India")
        # Broaden the default query to surface internships + fresher roles too.
        self.default_query = os.getenv(
            "JOOBLE_DEFAULT_QUERY",
            "software engineer OR data analyst OR AI ML intern OR fresher")

    def available(self) -> bool:
        return bool(self.key)

    def status_message(self) -> str:
        return ("Connected to Jooble (official API)." if self.key
                else "Jooble needs a free API key (set JOOBLE_API_KEY).")

    async def fetch(self, client, query: str, location: str, limit: int) -> List[RawJob]:
        if not self.key:
            return []
        payload = {
            "keywords": (query or self.default_query),
            "location": (location or self.default_location),
        }
        try:
            r = await client.post(ENDPOINT.format(key=self.key), json=payload)
            r.raise_for_status()
            jobs = r.json().get("jobs", []) or []
        except Exception:
            return []
        out: List[RawJob] = []
        for j in jobs[:limit]:
            title = j.get("title", "") or ""
            loc = j.get("location", "") or ""
            snippet = j.get("snippet", "") or ""
            out.append(RawJob(
                source=self.name,
                title=title,
                company=j.get("company", "") or "",
                apply_url=j.get("link", ""),          # genuine listing → Track & Apply
                location=loc,
                salary=j.get("salary", "") or "",
                remote="remote" in loc.lower() or "work from home" in snippet.lower(),
                job_type=j.get("type", "") or "",
                # Classify internship / fresher / job so the tabs + filters work.
                employment_type=infer_employment_type(title),
                posted_at=(j.get("updated") or "")[:10],
                description_snippet=snippet,
                external_id=f"jooble-{j.get('id')}",
                company_domain="",                    # → Generic adapter (Track & Apply only)
            ))
        return out
