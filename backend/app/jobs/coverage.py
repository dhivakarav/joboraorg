"""Source-coverage analytics — Internshala breakdown.

Counts Internshala internships surfaced in Jobora, regardless of which provider
delivered them: the native Internshala feed (when licensed) AND Internshala-hosted
listings that already arrive lawfully via JSearch (Google for Jobs). Pure functions
over JobOut/RawJob-like objects; no network.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse
from typing import Iterable

_AIML_RE = re.compile(
    r"\b(ai|ml|machine\s*learning|deep\s*learning|data\s*scien(?:ce|tist)|"
    r"data\s*analyst|nlp|computer\s*vision|artificial\s*intelligence)\b", re.I)
_SWE_RE = re.compile(
    r"\b(software|sde|swe|back[-\s]?end|front[-\s]?end|full[-\s]?stack|developer|"
    r"web\s*develop|programmer|python|java(script)?)\b", re.I)


def is_internshala_url(url: str) -> bool:
    """True if an apply URL is hosted on internshala.com (any provider)."""
    host = urlparse(url or "").netloc.lower()
    return host == "internshala.com" or host.endswith(".internshala.com")


def is_internshala(job) -> bool:
    """A job counts as Internshala if its source is the Internshala provider OR its
    apply URL is internshala.com (e.g. an Internshala listing surfaced via JSearch)."""
    return (getattr(job, "source", "") == "Internshala"
            or is_internshala_url(getattr(job, "apply_url", "")))


def internshala_breakdown(jobs: Iterable) -> dict:
    """Source analytics for the Internshala slice of a result set."""
    insh = [j for j in jobs if is_internshala(j)]

    def et(j):
        return (getattr(j, "employment_type", "") or "").lower()

    def title(j):
        return getattr(j, "title", "") or ""

    return {
        "internshala_total": len(insh),
        "internships": sum(1 for j in insh if et(j) == "internship"),
        "fresher": sum(1 for j in insh if et(j) == "fresher"
                       or getattr(j, "early_signal", "") in ("Fresher Friendly", "New Grad")),
        "ai_ml": sum(1 for j in insh if _AIML_RE.search(title(j))),
        "software": sum(1 for j in insh if _SWE_RE.search(title(j))),
    }
