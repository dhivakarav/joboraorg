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


def _cached_fallback(provider, query: str, location: str) -> List[RawJob]:
    """Most recent cached fetch for a provider (any age), trying the recent-search
    and normal cache keys. Used when a provider is too slow to finish within the
    search deadline — we serve its last-known jobs rather than nothing."""
    base = _provider_key(provider, query, location)
    for pk in (base + "|recent", base):
        hit = _provider_cache.get(pk)
        if hit and hit[1]:
            return hit[1]
    return []


def _cache_key(query: str, location: str, keywords: List[str]) -> str:
    body = f"{query.lower().strip()}|{location.lower().strip()}|{','.join(sorted(k.lower() for k in keywords))}"
    return _CACHE_PREFIX + body


def provider_status() -> List[dict]:
    out = []
    for p in ALL_PROVIDERS:
        entry = {
            "name": p.name,
            "available": p.available(),
            "requires_key": p.requires_key,
            "official_api": p.official_api,
            "status": p.status(),                       # Connected | Disabled | Mock Mode | …
        }
        # Providers with a richer lifecycle expose extra signals (Internshala).
        if hasattr(p, "authorized"):
            entry["authorized"] = p.authorized()
        if hasattr(p, "status_message"):
            entry["status_message"] = p.status_message()
        out.append(entry)
    return out


async def _call_provider(provider, client, query, location, limit, use_cache=True,
                         recent=False) -> List[RawJob]:
    """Run one provider with provider-level caching, rate limiting + error isolation."""
    if not provider.available():
        return []

    # Recent (Refresh) requests must NOT read the provider cache, and are cached
    # under a distinct key so a normal search never serves the recency-sorted set.
    pk = _provider_key(provider, query, location) + ("|recent" if recent else "")
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
        # Only paginating providers (Adzuna/JSearch) accept recent=; others keep the
        # base signature. supports_recent gates the keyword so we never break them.
        if getattr(provider, "supports_recent", False):
            coro = provider.fetch(client, query, location, limit, recent=recent)
        else:
            coro = provider.fetch(client, query, location, limit)
        jobs = await asyncio.wait_for(coro, timeout=settings.PROVIDER_TIMEOUT)
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
    recent: bool = False,
) -> List[dict]:
    keywords = keywords or []
    key = _cache_key(query, location, keywords) + f"|{employment_type}" + ("|recent" if recent else "")

    if use_cache:
        cached = cache.get(key)
        if cached:
            return cached[:limit]

    # Decouple how MANY we pull from how many we display. A normal (cached) search
    # pulls a generous pool — bounded only by each provider's pagination cap + real
    # free-tier API limits, never an arbitrary internal number — and is cached for
    # 15 min, so the cost is amortised. A REFRESH (live, uncached) instead wants the
    # FRESHEST jobs FAST, not the deepest pool, so it uses a lighter budget to keep
    # the live round-trip well within the wall-clock deadline below.
    fetch_budget = limit if recent else max(limit, settings.PROVIDER_FETCH_BUDGET)

    headers = {"User-Agent": "JoboraBot/1.0 (+https://jobora.app; job-aggregator)"}
    async with httpx.AsyncClient(timeout=settings.PROVIDER_TIMEOUT, headers=headers,
                                 follow_redirects=True) as client:
        # Warm live FX rates so salary→INR conversion is current (best-effort, short).
        from .currency import _refresh_rates
        try:
            await asyncio.wait_for(_refresh_rates(client), timeout=3)
        except Exception:
            pass   # stale FX is fine; never let it block discovery

        # HARD WALL-CLOCK DEADLINE: launch every provider concurrently, then wait at
        # most SEARCH_DEADLINE_SECONDS. Providers that finish contribute; slow ones
        # are cancelled and simply skipped for THIS search (they're still cached from
        # earlier runs and will return next time). This guarantees the request always
        # returns promptly — a single slow provider (e.g. JSearch's ~11s round-trip)
        # can no longer push the whole response past a client/proxy socket timeout.
        tasks = [asyncio.ensure_future(
                    _call_provider(p, client, query, location, fetch_budget, use_cache, recent))
                 for p in ALL_PROVIDERS]
        done, pending = await asyncio.wait(tasks, timeout=settings.SEARCH_DEADLINE_SECONDS)
        for t in pending:
            t.cancel()
        if pending:
            # Let cancellations settle so the httpx client closes cleanly on exit.
            await asyncio.gather(*pending, return_exceptions=True)
            slow = [p.name for p, t in zip(ALL_PROVIDERS, tasks) if t in pending]
            print(f"[aggregator] deadline {settings.SEARCH_DEADLINE_SECONDS}s hit; "
                  f"slow providers this run served from cache: {slow}")
        results = []
        for p, t in zip(ALL_PROVIDERS, tasks):
            if t in done and not t.cancelled() and t.exception() is None:
                results.append(t.result())
            else:
                # Cancelled straggler (too slow this run): fall back to its most
                # recent cached fetch so a slow-but-sole source (e.g. JSearch for
                # Dubai) still contributes its freshest-known jobs instead of zero.
                results.append(_cached_fallback(p, query, location))

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

    # When a SPECIFIC non-India location is searched (e.g. Dubai, Singapore), jobs
    # actually in that location must survive the `limit` cut — otherwise verified
    # global/remote jobs that merely passed the filter crowd them out before the
    # API/UI ever sees them. Stable sort, so it only reorders by location match.
    from . import india
    loc_q = (location or "").strip().lower()
    if loc_q and not india.is_india_filter(loc_q):
        serialised.sort(key=lambda d: 0 if loc_q in (d.get("location") or "").lower() else 1)

    # Refresh: surface the most recently posted jobs first (newest on top), so each
    # explicit refresh shows fresh listings rather than the verified-first ordering.
    if recent:
        serialised.sort(key=lambda d: d.get("posted_at") or "", reverse=True)

    cache.set(key, serialised, ttl=settings.JOB_CACHE_TTL)
    return serialised[:limit]


def clear_cache():
    cache.clear_prefix(_CACHE_PREFIX)
