"""Fixed-window rate limiting, backed by the cache layer (Redis or in-memory).

Used to close the CRITICAL "no rate limiting" finding:
  - brute-force protection on login/register (per client IP)
  - abuse/DoS protection on the browser-launching apply endpoint (per user)
  - cost/abuse protection on job search (per user)

Call ``enforce(scope, identity, limit, window)`` from a route; it raises
HTTP 429 with a Retry-After header when the limit is exceeded.
"""
from __future__ import annotations

from fastapi import HTTPException, Request

from .cache import cache
from .config import settings


def client_ip(request: Request) -> str:
    """Best-effort client IP, honoring the first hop of X-Forwarded-For."""
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce(scope: str, identity: str, limit: int, window: int) -> None:
    """Raise 429 if `identity` has exceeded `limit` actions in `window` seconds."""
    if not settings.RATE_LIMIT_ENABLED:
        return
    key = f"rl:{scope}:{identity}"
    count = cache.incr(key, window)
    if count > limit:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded for {scope}. Try again later.",
            headers={"Retry-After": str(window)},
        )
