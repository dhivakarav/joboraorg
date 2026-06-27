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
    """Return the real client IP for rate-limiting.

    Trust X-Real-IP first — nginx sets this to $remote_addr (the actual TCP
    peer) and it cannot be forged by the client. Fall back to X-Forwarded-For
    only when running without nginx (direct uvicorn in dev/tests), and in that
    case use the LAST hop so an upstream proxy can't be faked by prepending
    extra IPs. Never trust client-supplied X-Forwarded-For in production.
    """
    # X-Real-IP is set by nginx to $remote_addr — unforgeable behind our proxy.
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip
    # Direct uvicorn (dev/tests): fall back to the TCP peer address.
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
