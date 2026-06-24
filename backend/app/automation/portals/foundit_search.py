"""Foundit (formerly Monster India) — SEARCH-LINK ONLY. No public API, no scraping.

Foundit's robots.txt + ToS disallow automated listing access and it runs
anti-bot protection. We NEVER fetch/parse Foundit — this only builds a public
search deep-link the user opens to apply on Foundit directly.
"""
from __future__ import annotations

from urllib.parse import urlencode

NAME = "Foundit"
DOMAIN = "foundit.in"
AUTO_APPLY = False
SCRAPES = False


def search_link(query: str = "", location: str = "India") -> str:
    return "https://www.foundit.in/srp/results?" + urlencode(
        {"query": query or "jobs", "locations": location or "India"})
