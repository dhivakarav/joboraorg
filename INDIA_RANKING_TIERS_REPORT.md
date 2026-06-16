# India-First Tiered Ranking — Verification Report

_Date: 2026-06-16. Implemented + verified. Backend ranking only; no provider,
filter, or apply-flow changes._

## What changed
A **tier** is now the PRIMARY ranking key, so India always outranks US/EU regardless
of match score. Within a tier, the existing relevance order (`_rank_key`) is preserved.

| Tier | Definition | Constant |
|---|---|---|
| **Tier 1** | India-located, on-site (e.g. "Bengaluru, India", "Hyderabad, IN") | `TIER_INDIA = 1` |
| **Tier 2** | India-located AND remote (e.g. "Remote, India") | `TIER_INDIA_REMOTE = 2` |
| **Tier 3** | Everything else — US/EU/global, incl. non-India "Remote" | `TIER_GLOBAL = 3` |

### Files
| File | Change |
|---|---|
| `app/jobs/india.py` | New `india_tier(location, remote)` + `TIER_*` constants (uses `_is_india`, which handles the `", IN"`/`"IN"` country code). |
| `app/routers/jobs.py` | Sort changed from `sort(key=_rank_key, reverse=True)` → `sort(key=lambda j: (india.india_tier(j.location, j.remote), -_rank_key(j)))`. Tier primary, relevance secondary. |
| `tests/test_india.py` | +6 regression tests. |

## Requirements coverage
| # | Requirement | Status |
|---|---|---|
| 1 | Tiers: India / India-remote / Global | ✅ `india_tier` (Tier 1/2/3) |
| 2 | Sort by tier first, then match score | ✅ `(tier, -_rank_key)`; `_rank_key` is match/eligibility/domain |
| 3a | India jobs always rank above US jobs | ✅ test (India low match still beats US high match) |
| 3b | India-remote ranks above US remote | ✅ test |
| 3c | Match-score ordering unchanged within a tier | ✅ test (equal eligibility → higher match first) |
| 4 | Backend tests + frontend build | ✅ 80 passed / build clean |
| 5 | Verification report | ✅ this file |

## Evidence

### Regression tests (6 new, all pass)
- `test_india_tier_classification` — `", IN"` + city/hub → Tier 1/2; generic "Remote" + US/EU → Tier 3; `TIER_INDIA < TIER_INDIA_REMOTE < TIER_GLOBAL`.
- `test_india_always_ranks_above_us_even_with_higher_us_match` — India(match 10) **beats** US(match 99).
- `test_india_remote_ranks_above_us_remote` — `GitLabIN` (Remote, India) before `NotionUS` (Remote, US).
- `test_tier_order_india_then_india_remote_then_global` — order = India → India-remote → global.
- `test_match_score_ordering_unchanged_within_tier` — within Tier 1: match 80 > 60 > 40.
- `test_match_ordering_within_global_tier` — within Tier 3: match 90 > 30.

### Live router on a mixed feed
```
T1 | Bengaluru, India   | Razorpay-IN      ← India on-site
T1 | Chennai, India     | Zoho-IN
T2 | Remote, India      | GitLab-INrem     ← India remote
T3 | Remote, US         | Notion-USrem     ← global
T3 | San Francisco, CA  | Stripe-US
T3 | Berlin, Germany    | TecFox-EU
```

### Test + build
- `pytest` → **80 passed** (was 74; +6 tier tests). No regressions.
- `npm run build` → clean (60 modules).

## Notes
- The pre-existing `india_bonus` in `_rank_key` is now redundant for cross-tier ordering
  (the tier dominates) but harmless — within a tier it's a constant, so it doesn't affect
  in-tier order. Left in place to avoid touching the established relevance score.
- Orthogonal open item (frontend, from prior audit): the Location dropdown doesn't
  re-query on change — unrelated to this ranking work.
