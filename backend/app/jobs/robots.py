"""robots.txt compliance checker.

Used to gate any HTML-scraping provider: before fetching a path we confirm the
site's robots.txt actually allows it for our user-agent. Official JSON APIs
(Greenhouse, Lever, Adzuna, …) are exempt because they are published,
documented endpoints intended for programmatic access — but we still expose
this so scraping providers can be added safely and lawfully.
"""
from __future__ import annotations

import time
import urllib.robotparser as robotparser
from urllib.parse import urlparse

USER_AGENT = "JoboraBot/1.0 (+https://jobora.app/bot; job-aggregator)"

# Cache parsed robots files for an hour to avoid hammering sites.
_CACHE: dict[str, tuple[float, robotparser.RobotFileParser]] = {}
_TTL = 3600.0


def _get_parser(base: str) -> robotparser.RobotFileParser | None:
    now = time.time()
    cached = _CACHE.get(base)
    if cached and now - cached[0] < _TTL:
        return cached[1]
    rp = robotparser.RobotFileParser()
    rp.set_url(f"{base}/robots.txt")
    try:
        rp.read()
    except Exception:
        # If robots.txt can't be fetched, be conservative and disallow scraping.
        _CACHE[base] = (now, None)  # type: ignore
        return None
    _CACHE[base] = (now, rp)
    return rp


def can_fetch(url: str) -> bool:
    """Return True only if robots.txt explicitly allows our agent to fetch url."""
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return False
    base = f"{parsed.scheme}://{parsed.netloc}"
    rp = _get_parser(base)
    if rp is None:
        return False
    try:
        return rp.can_fetch(USER_AGENT, url)
    except Exception:
        return False
