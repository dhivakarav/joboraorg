"""Aggregates real jobs across all configured providers.

Responsibilities:
  - fan out to every available provider concurrently (httpx async)
  - isolate failures so one bad provider never breaks a search
  - enforce a per-provider rate limit (min interval between live calls)
  - normalise, filter, dedupe, and verify results
  - TTL-cache search results to avoid redundant upstream calls
"""
from __future__ import annotations

import asyncio
import time
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx

from ..cache import cache
from ..config import settings
from .base import RawJob, matches_filters
from .providers import ALL_PROVIDERS


def _canonical_url(url: str) -> str:
    """Normalise an apply URL for cross-provider dedupe: host + path, lowercased,
    no scheme/query/fragment/trailing slash. So the same listing arriving from
    Internshala and JSearch collapses to one key."""
    if not url:
        return ""
    p = urlparse(url.strip())
    host = (p.netloc or "").lower().lstrip("www.")
    path = (p.path or "").rstrip("/").lower()
    return f"{host}{path}" if host else ""

# ---- rate-limit state (process-local; fine per instance) ----
_provider_last_call: Dict[str, float] = {}
_CACHE_PREFIX = "jobs:search:"

# ---- provider-level result cache (process-local TTL) ----
# Caches each provider's RAW fetch so any subsequent search reuses it. Query-
# agnostic providers (big-tech boards) are cached once and reused for ALL queries
# — the slow board fetches stop dominating cold searches after the first call.
_provider_cache: Dict[str, Tuple[float, List[RawJob]]] = {}


def _provider_key(provider, query: str, location: str) -> str:
    q = "" if getattr(provider, "query_agnostic", False) else query.lower().strip()
    return f"{provider.name}|{q}|{location.lower().strip()}"


def clear_provider_cache():
    _provider_cache.clear()


def _cache_key(query: str, location: str, keywords: List[str]) -> str:
    body = f"{query.lower().strip()}|{location.lower().strip()}|{','.join(sorted(k.lower() for k in keywords))}"
    return _CACHE_PREFIX + body


def provider_status() -> List[dict]:
    out = []
    for p in ALL_PROVIDERS:
        out.append({
            "name": p.name,
            "available": p.available(),
            "requires_key": p.requires_key,
            "official_api": p.official_api,
        })
    return out


async def _call_provider(provider, client, query, location, limit, use_cache=True) -> List[RawJob]:
    """Run one provider with provider-level caching, rate limiting + error isolation."""
    if not provider.available():
        return []

    pk = _provider_key(provider, query, location)
    if use_cache:
        hit = _provider_cache.get(pk)
        if hit and hit[0] > time.time():
            return hit[1]

    now = time.time()
    last = _provider_last_call.get(provider.name, 0)
    wait = settings.PROVIDER_MIN_INTERVAL - (now - last)
    if wait > 0:
        await asyncio.sleep(min(wait, settings.PROVIDER_MIN_INTERVAL))
    _provider_last_call[provider.name] = time.time()
    try:
        jobs = await asyncio.wait_for(
            provider.fetch(client, query, location, limit),
            timeout=settings.PROVIDER_TIMEOUT,
        )
        _provider_cache[pk] = (time.time() + settings.JOB_CACHE_TTL, jobs)
        return jobs
    except Exception as exc:  # isolate: a failing provider yields nothing
        print(f"[aggregator] provider {provider.name} failed: {exc}")
        # Serve stale provider data if we have any, rather than nothing.
        stale = _provider_cache.get(pk)
        return stale[1] if stale else []


async def search(
    query: str = "",
    location: str = "",
    keywords: Optional[List[str]] = None,
    limit: int = 60,
    use_cache: bool = True,
    employment_type: str = "",
) -> List[dict]:
    keywords = keywords or []
    key = _cache_key(query, location, keywords) + f"|{employment_type}"

    if use_cache:
        cached = cache.get(key)
        if cached:
            return cached[:limit]

    headers = {"User-Agent": "JoboraBot/1.0 (+https://jobora.app; job-aggregator)"}
    async with httpx.AsyncClient(timeout=settings.PROVIDER_TIMEOUT, headers=headers,
                                 follow_redirects=True) as client:
        # Warm live FX rates so salary→INR conversion is current.
        from .currency import _refresh_rates
        await _refresh_rates(client)
        results = await asyncio.gather(
            *[_call_provider(p, client, query, location, limit, use_cache) for p in ALL_PROVIDERS]
        )

    # Flatten + validate.
    raw: List[RawJob] = []
    for chunk in results:
        raw.extend(j for j in chunk if j.is_valid())

    # Filter for relevance (+ employment type: internship/fresher/job).
    filtered = [j for j in raw if matches_filters(j, query, location, keywords, employment_type)]

    # Internshala precedence: the native Internshala feed carries richer metadata
    # (stipend, duration, skills) than a JSearch/Adzuna echo of the same listing,
    # so process Internshala-source records first — they win the canonical-URL
    # dedupe below over duplicates from other providers.
    filtered.sort(key=lambda j: 0 if j.source == "Internshala" else 1)

    # Dedupe by fingerprint AND by canonical apply URL (so the same internship
    # arriving via Internshala + JSearch is shown once).
    seen: set = set()
    seen_urls: set = set()
    deduped: List[RawJob] = []
    for j in filtered:
        fp = j.fingerprint
        cu = _canonical_url(j.apply_url)
        if fp in seen or (cu and cu in seen_urls):
            continue
        seen.add(fp)
        if cu:
            seen_urls.add(cu)
        deduped.append(j)

    # Verified jobs first, then most recently posted.
    serialised = [j.to_dict() for j in deduped]
    serialised.sort(key=lambda d: (not d["verified"], d.get("posted_at") or ""), reverse=False)
    serialised.sort(key=lambda d: d.get("posted_at") or "", reverse=True)
    serialised.sort(key=lambda d: not d["verified"])  # verified first, stable

    cache.set(key, serialised, ttl=settings.JOB_CACHE_TTL)
    return serialised[:limit]


def clear_cache():
    cache.clear_prefix(_CACHE_PREFIX)
