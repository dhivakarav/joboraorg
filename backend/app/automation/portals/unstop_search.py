"""Unstop — SEARCH-LINK ONLY. No public application API, no scraping, no auto-submit.

Unstop (formerly Dare2Compete) has no public/documented application API for
third-party developers, and its ToS/robots.txt disallow scraping its listing
pages. So — exactly like naukri_search.py / indeed_search.py / linkedin_search.py
/ foundit_search.py — this module NEVER fetches or parses unstop.com. It only
BUILDS a public search deep-link the user opens in a new tab to apply on Unstop
directly (internships, fresher jobs & hackathon-linked hiring).

Individual Unstop listings (with match scores) reach Jobora only if a licensed
aggregator (JSearch/Adzuna) returns rows whose apply_url points to unstop.com —
those are surfaced as ordinary manual-apply rows (labelled "Apply on Unstop"),
match-scored and threshold-filtered like every other manual source.
"""
from __future__ import annotations

from urllib.parse import urlencode

NAME = "Unstop"
DOMAIN = "unstop.com"
AUTO_APPLY = False          # no public application API
SCRAPES = False             # never fetches the site


def search_link(query: str = "", location: str = "India") -> str:
    """Public Unstop jobs/internships search URL (read-only deep link; no fetch)."""
    term = " ".join(p for p in [(query or "").strip(), (location or "").strip()] if p)
    return "https://unstop.com/jobs?" + urlencode({"searchTerm": term or "internships"})
