"""Naukri — SEARCH-LINK ONLY. No public API, no scraping, no login, no auto-submit.

Naukri's robots.txt + ToS disallow scraping its listing pages and it runs
anti-bot protection, so we NEVER fetch or parse Naukri. This module only BUILDS a
public search deep-link the user opens in a new tab to apply on Naukri directly.
Individual Naukri listings (with match scores) reach Jobora only via licensed
aggregator APIs (JSearch/Adzuna) whose apply_url points back to naukri.com.
"""
from __future__ import annotations

NAME = "Naukri"
DOMAIN = "naukri.com"
AUTO_APPLY = False          # no public application API
SCRAPES = False             # never fetches the site


def _slug(s: str) -> str:
    return "-".join((s or "").strip().lower().split())


def search_link(query: str = "", location: str = "India") -> str:
    """Public Naukri search URL (read-only deep link; no fetch)."""
    q = _slug(query) or "jobs"
    loc = _slug(location) or "india"
    return f"https://www.naukri.com/{q}-jobs-in-{loc}"
