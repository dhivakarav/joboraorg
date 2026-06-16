# Internshala Provider — Implemented

_Implemented 2026-06-16. Compliant maximal build: a **feed-gated** provider (real
data the moment a licensed `INTERNSHALA_FEED_URL` is configured) + Internshala-aware
dedupe, analytics, and deep-link apply. **No scraping, no apply automation, never
fetches internshala.com HTML.** See `INTERNSHALA_FEASIBILITY_REPORT.md` for why a
licensed feed is the only lawful data path._

## What was built
| Goal | Implementation | File |
|---|---|---|
| 1. Surface Internshala internships | Feed-gated provider maps a licensed feed → `RawJob`; also surfaces Internshala listings that arrive via JSearch (analytics/dedup) | `app/jobs/providers/internshala.py` |
| 2. Resume matching | Flows through the existing `score_job`/matching engine; skills stored in snippet | (existing pipeline) |
| 3. India internships above global | All records India-tagged → `india_tier` Tier 1/2 → existing tiered sort ranks them above US/EU | `internshala.py` + `india.py` |
| 4. Dedupe vs JSearch/Adzuna | Canonical-URL dedupe + Internshala-source precedence in the aggregator | `app/jobs/aggregator.py` |
| 5. "Apply on Internshala" deep link | `InternshalaAdapter` is `manual_only` → Track & Apply opens `apply_url`, records Tracked | `app/adapters/internshala.py` |
| 6. Store metadata | title, company, stipend (→INR), location, duration, **skills** (in snippet), apply URL | `internshala.py` `_to_rawjob` |
| 7. Source analytics | `internshala_breakdown()` → total / internships / fresher / ai_ml / software; surfaced in `JobSearchOut.internshala_coverage` + analytics | `app/jobs/coverage.py`, `routers/jobs.py` |

## Architecture
```
licensed feed (INTERNSHALA_FEED_URL)
        │  (host guard: never internshala.com HTML unless TRUSTED)
        ▼
InternshalaProvider.fetch ──► RawJob (India-tagged, stipend, duration, skills)
        │
aggregator: matches_filters → canonical-URL dedupe (Internshala wins) → cache
        │
router: _decorate → eligibility → filters → sort(india_tier, -_rank_key)
        │                                     └ Tier 1/2 (India) above Tier 3
        ▼
JobSearchOut.items  +  internshala_coverage analytics
        │
frontend: Greenhouse→submit, Lever/Ashby→assisted, else → Track & Apply (deep-link)
```

## Compliance posture (verified)
- **Provider is gated:** `available()` is `False` until `INTERNSHALA_FEED_URL` is set.
- **No-scrape guard:** `fetch()` refuses any feed URL on `internshala.com` unless
  `INTERNSHALA_FEED_TRUSTED=1` (a licensed endpoint). It never fetches Internshala HTML.
- **Robots gate caveat:** `can_fetch()` fails open on Internshala's robots.txt
  (documented in the feasibility report); the host guard above does **not** rely on
  it. *(Follow-up: harden `app/jobs/robots.py` — tracked in the implementation plan.)*
- **Apply is a hand-off only** (`manual_only=True`); never assisted/automated.

## Metadata stored (`RawJob`/`JobOut`)
`title`, `company`, `salary`/`salary_inr` (stipend → INR via currency module),
`location` (India-tagged), `duration`, `apply_url`, `external_id`, `employment_type`,
`remote`; **skills** are stored in `description_snippet` as `"Skills: …"` (matchable
by the resume engine; `RawJob` has no dedicated skills field).

## Verification (all mocked — no network, no internshala.com)
- `tests/test_internshala.py` → **11 passed**: gating, **no-scrape host guard**, feed
  mapping, skills metadata, India Tier 1/2, canonical-URL dedupe, `is_internshala`
  detection, analytics breakdown.
- End-to-end mock-feed run: 3 records → Tier 1 (Bengaluru, Pune) + Tier 2 (work-from-
  home), correct stipend/duration/skills, analytics `{total:3, internships:2,
  fresher:1, ai_ml:1, software:2}`.
- Full suite **94 passed**; `npm run build` clean.

## Configuration (to go live)
```
INTERNSHALA_FEED_URL=https://<licensed-partner-feed>      # required to activate
INTERNSHALA_FEED_TRUSTED=1                                 # if the host needs robots bypass
```
Feed JSON: a list, or `{"internships": [...]}`, with per-record fields:
`id, title, company|company_name, stipend|salary, location, duration, skills (list|csv),
type, url|apply_url, description, posted_at, deadline`.

---

## Implementation plan (status)
| Phase | Work | Status |
|---|---|---|
| **0 — provider + India-tier + skills + host guard** | code | ✅ **Done** |
| **0b — dedupe vs JSearch/Adzuna (canonical URL + precedence)** | code | ✅ **Done** |
| **0c — source analytics (`coverage.py`, `internshala_coverage`)** | code | ✅ **Done** |
| **0d — deep-link apply** | reuses Track & Apply | ✅ **Done** |
| 1 — harden `robots.py` (can_fetch fail-open fix) | code | ⏳ Recommended follow-up (~0.5 d) |
| 2 — secure a licensed feed | business | ⛔ External (partnership) |
| 3 — activate + live coverage report | config + verify | ⏳ Blocked on Phase 2 |

**Everything code-side is done and tested.** Live discovery is one config value
(`INTERNSHALA_FEED_URL`) away — blocked only on a licensed feed (business track).

## Maintenance estimate
| Aspect | Burden | Notes |
|---|---|---|
| Provider mapping | **Low** | Small `_to_rawjob`; breaks only if the licensed feed changes schema |
| Dedupe / tiering / analytics | **Very low** | Shared logic (`india.py`, `aggregator.py`, `coverage.py`); no Internshala-specific ranking |
| Compliance | **Low** | Host guard is static; robots posture is the partner's responsibility under the feed agreement |
| Apply flow | **None** | Hand-off only; nothing to maintain |
| **Overall** | **Low (~0.5 day/yr)** | Dominated by feed-schema drift if/when a feed exists; zero upkeep while gated |
