# Search Performance — Report (High H1)

Cut cold/warm job-search latency by adding **provider-level caching** on top of the
existing aggregate-result cache. No matching/integrity/board changes; no new boards.

## Problem
A job search fans out to ~10 live providers. The big-tech **board providers**
(Greenhouse 10 boards, Lever 8 companies, Ashby 6 boards, Arbeitnow) dominate the
cold path. The aggregate cache only helped the *exact same* query; a different
query re-fetched everything (~5.6–10.4s observed).

## Fix
1. **`query_agnostic` flag** on providers whose `fetch()` ignores the query and
   returns a broad list (Greenhouse, Lever, Ashby, Arbeitnow). Their raw fetch is
   cached **once** and reused for **every** query (filtering still happens after).
2. **Provider-level TTL cache** (`_provider_cache`) in the aggregator keyed by
   `provider | query(or "" if agnostic) | location`, TTL = `JOB_CACHE_TTL` (900s).
   Query-specific providers (Remotive/Adzuna/Jooble) still key by query.
3. **Stale-on-error**: if a provider call fails, cached data is served instead of
   dropping the provider's results.
4. Existing **aggregate cache** retained for exact-query repeats.

## Measured before / after (real providers)
| Scenario | Latency | Jobs |
|---|---|---|
| **Cold** (all caches empty) — `software engineer` | **5,646 ms** | 60 |
| New query `data analyst` (boards cached) | **769 ms** | 60 |
| New query `marketing intern` (boards cached) | **830 ms** | 60 |
| New query `product manager` (boards cached) | 3,515 ms | 60 |
| **Repeat** `data analyst` (aggregate hit) | **3 ms** | 60 |

- **Different-query searches: ~5.6s → ~0.8s typical** (≈7× faster) — the slow board
  fetches are eliminated after the first call.
- **Repeat searches: ~instant (3 ms).**
- Residual variance (e.g. `product manager` 3.5s) is the **query-specific** APIs
  (Remotive) which still fetch live per new query, then cache by query.

## Notes / honesty
- Provider cache is **process-local** (per instance). The Redis aggregate cache is
  shared across replicas; provider cache warms per instance on first use — fine,
  and warms fast.
- Frontend already shows a `<Spinner/>` during the cold fetch; no UI change needed.
- `clear_provider_cache()` added for refresh/admin use.

## Verification
- Latency measured via the aggregator directly (above).
- 21/21 backend tests pass; no change to result content (still 60 real jobs,
  same ranking/eligibility).
