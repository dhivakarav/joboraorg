"""Indeed India — SEARCH-LINK ONLY. No public API, no scraping, no auto-submit.

Indeed's robots.txt + ToS disallow automated access to its listings and it runs
anti-bot protection. We NEVER fetch/parse Indeed — this only builds a public
search deep-link. Individual Indeed listings arrive via licensed aggregator APIs
(JSearch/Adzuna) whose apply_url points back to Indeed.
"""
from __future__ import annotations

from urllib.parse import urlencode

NAME = "Indeed"
DOMAIN = "indeed.com"
AUTO_APPLY = False
SCRAPES = False


def search_link(query: str = "", location: str = "India") -> str:
    return "https://in.indeed.com/jobs?" + urlencode({"q": query or "jobs",
                                                       "l": location or "India"})
