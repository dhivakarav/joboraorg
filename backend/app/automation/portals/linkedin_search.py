"""LinkedIn — SEARCH-LINK ONLY. No public jobs API, no scraping, no auto-submit.

LinkedIn's ToS strictly prohibit scraping/automation and it actively enforces
anti-bot protection (and litigates scraping). We NEVER fetch/parse LinkedIn —
this only builds a public job-search deep-link the user opens to apply on
LinkedIn directly.
"""
from __future__ import annotations

from urllib.parse import urlencode

NAME = "LinkedIn"
DOMAIN = "linkedin.com"
AUTO_APPLY = False
SCRAPES = False


def search_link(query: str = "", location: str = "India") -> str:
    return "https://www.linkedin.com/jobs/search/?" + urlencode(
        {"keywords": query or "jobs", "location": location or "India"})
