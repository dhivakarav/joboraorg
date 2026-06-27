"""Cache abstraction: Redis in production, in-memory fallback for local/dev.

A single ``cache`` object is imported across the app. When ``REDIS_URL`` is set
and reachable, values are stored in Redis (shared across processes/instances —
required to scale horizontally). Otherwise it transparently falls back to a
process-local dict with TTL, so the app runs with zero infra.

Values are JSON-serialised, so store plain dict/list/str/number payloads.
"""
from __future__ import annotations

import json
import threading
import time
from typing import Any, Optional

from .config import settings

_redis = None
_redis_tried = False


def _get_redis():
    global _redis, _redis_tried
    if _redis_tried:
        return _redis
    _redis_tried = True
    if not settings.REDIS_URL:
        return None
    try:
        import redis
        client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        client.ping()
        _redis = client
        print("[cache] using Redis")
    except Exception as exc:
        print(f"[cache] Redis unavailable ({exc}); using in-memory fallback")
        _redis = None
    return _redis


class _MemoryCache:
    def __init__(self):
        self._store: dict[str, tuple[float, str]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            item = self._store.get(key)
            if not item:
                return None
            expires, value = item
            if expires and expires < time.time():
                self._store.pop(key, None)
                return None
            return value

    def setex(self, key: str, ttl: int, value: str):
        with self._lock:
            self._store[key] = (time.time() + ttl if ttl else 0, value)

    def delete_prefix(self, prefix: str):
        with self._lock:
            for k in [k for k in self._store if k.startswith(prefix)]:
                self._store.pop(k, None)


_memory = _MemoryCache()


class Cache:
    """Unified JSON cache facade over Redis or the in-memory store."""

    @property
    def backend(self) -> str:
        return "redis" if _get_redis() is not None else "memory"

    def get(self, key: str) -> Optional[Any]:
        r = _get_redis()
        raw = r.get(key) if r is not None else _memory.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return None

    def set(self, key: str, value: Any, ttl: int = 900):
        raw = json.dumps(value)
        r = _get_redis()
        if r is not None:
            r.setex(key, ttl, raw)
        else:
            _memory.setex(key, ttl, raw)

    def clear_prefix(self, prefix: str):
        r = _get_redis()
        if r is not None:
            for k in r.scan_iter(match=f"{prefix}*"):
                r.delete(k)
        else:
            _memory.delete_prefix(prefix)

    def incr(self, key: str, window: int) -> int:
        """Increment a counter, setting a TTL of `window` seconds on first use.

        Returns the current count. Used for fixed-window rate limiting. Works on
        Redis (atomic INCR + EXPIRE) or the in-memory fallback.
        """
        r = _get_redis()
        if r is not None:
            pipe = r.pipeline()
            pipe.incr(key, 1)
            pipe.expire(key, window, nx=True)
            count, _ = pipe.execute()
            return int(count)
        # in-memory fallback — hold the lock for the entire read-modify-write so
        # concurrent async requests can't both read the same stale count.
        with _memory._lock:
            item = _memory._store.get(key)
            now = time.time()
            if item:
                expires, cur_val = item
                if expires and expires < now:
                    # window expired — start fresh
                    item = None
            if item is None:
                count = 1
                _memory._store[key] = (now + window, str(count))
            else:
                expires, cur_val = item
                count = int(cur_val) + 1
                ttl = max(1, int(expires - now))
                _memory._store[key] = (now + ttl, str(count))
        return count


cache = Cache()
