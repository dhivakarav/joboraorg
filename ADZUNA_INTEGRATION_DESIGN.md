# Adzuna Integration — Design Document (pre-implementation)

_Date: 2026-06-16. **Design only — no code changed.** Investigation of the existing
Adzuna provider + the changes needed to meet India-first v2 (tiered ranking)
standards. Implementation deferred pending approval._

## 1. Finding: the provider already exists and is lawful
`app/jobs/providers/adzuna.py` is **already implemented** against Adzuna's **official
public REST API** (`https://api.adzuna.com/v1/api/jobs/{country}/search/1`) — a real,
documented, ToS-permitted API (unlike Wellfound/Internshala, which have none). It:
- gates on `ADZUNA_APP_ID` + `ADZUNA_APP_KEY` (`available()` false until set),
- queries **India (`in`)** + Singapore (`sg`) by default; narrows by requested location,
- maps results → `RawJob` (title, company, redirect_url, location, salary, posted_at,
  `contract_time`, description, `external_id`),
- runs country fetches concurrently with error isolation.

**So integration is ~80% done.** The work is (a) obtaining keys and (b) closing gaps so
Adzuna behaves correctly under India-first v2. No scraping, no new legal risk.

## 2. Gap analysis vs. India-first v2

| # | Gap | Impact | Severity |
|---|---|---|---|
| **G1** | **Tier mis-classification.** `india_tier` reads the location string. Adzuna `in` results are *guaranteed* India, but `location.display_name` is often a **region only** (e.g. "Karnataka", "Maharashtra") not in `INDIA_HUBS` → `_is_india` returns False → real India jobs land in **Tier 3 (global)**. | India jobs sink below where they belong | **High** |
| G2 | **No internship/fresher signal.** Adzuna has no internship flag; `employment_type` is unset. Internship/fresher classification then relies solely on `base.infer_employment_type(title)`. | Some India internships miss the Internship/Fresher tabs | Medium |
| G3 | **Salary currency.** For `in`, `salary_min/max` are already INR, but the code builds a raw `"x - y CUR"` string; INR conversion happens downstream and may double-handle or mislabel. | Stipend display may be off | Medium |
| G4 | **No India-first default query.** When `q` is empty, no `what` param → generic results, not internship/priority-domain shaped (JSearch already does this via `default_query`). | Default feed less relevant | Low |
| G5 | **Singapore noise.** Default `in + sg` injects non-India (Tier 3) results. | Minor dilution | Low |
| G6 | **Page 1 only.** `results_per_page` ≤ 50, single page. | Caps breadth | Low |
| G7 | **No tests.** No `test_adzuna.py` (JSearch has one). | Regression risk | Medium |

## 3. Proposed design changes (when approved)

### G1 — guarantee India tagging for `in` results (must-fix)
In `_fetch_country`, when `country == "in"`, ensure the `RawJob.location` is India-tagged
so the tier function classifies it correctly. Cleanest: **append the ISO suffix** —
`location = f"{display_name}, IN"` (or just `"IN"` when blank). `india._is_india` already
recognizes the `", IN"` suffix, so all `in` results correctly become Tier 1/2. No change
to `india.py` needed.
- *Alternative:* set `remote` from `contract_time`/title and rely on tagging; not needed.

### G2 — employment type
Pass `employment_type=""` and let `base.infer_employment_type(title, "")` classify (it
already powers Internship/Fresher tabs for Greenhouse/Lever). Optionally map Adzuna
`category` ("graduate-jobs") → fresher. Low effort, improves tab coverage.

### G3 — salary → INR
For `in`, set `salary_currency = "INR"` explicitly and let the existing currency module
format `salary_inr`. Verify no double conversion (INR→INR should be a no-op).

### G4 — India-first default query
Mirror JSearch: when `q` is empty, default `what` to a priority-domain/internship blend
(reuse the JSearch default or a shared constant). Keep it overridable via
`ADZUNA_DEFAULT_QUERY`.

### G5 — India-only by default
Default to `["in"]` (drop `sg`) unless the user's location requests Singapore. Keeps the
feed India-first; `sg` stays reachable via an explicit location.

### G6 — optional pagination
Add `ADZUNA_PAGES` (default 1) to fetch N pages when more breadth is wanted; bounded to
respect quota.

### G7 — tests (`tests/test_adzuna.py`)
Mirror `test_jsearch.py` with a **mocked client** (no network): assert gating
(unavailable without keys), field mapping, **India tagging → Tier 1/2** (the G1 fix),
internship inference, and INR salary.

## 4. Quota & operations
- Adzuna free **developer tier** has documented **daily/throughput limits** (call-count
  capped per day). Mitigation already present: **provider-level + aggregate caching**
  (`JOB_CACHE_TTL`) + `PROVIDER_MIN_INTERVAL`.
- *Recommend:* the same lightweight request counter proposed for JSearch (admin signal
  when nearing the cap) — shared utility.
- Failures already isolated (`_fetch_country` swallows errors → empty list), so an Adzuna
  outage never breaks search.

## 5. Enablement steps (operator)
1. Register at `https://developer.adzuna.com` → get **App ID + App Key** (free).
2. Set `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` in `.env` (loaded by `_load_dotenv`).
3. Restart backend → provider flips to `available=True`; the "Adzuna · Source Pending"
   badge clears (frontend already lists it under `PENDING_SOURCES`).

## 6. Effort & sequencing
| Item | Effort | Blocker |
|---|---|---|
| Obtain keys + enable | minutes | none (free signup) |
| G1 India tagging (must-fix) | ~20 min | none |
| G2–G5 (type/salary/query/country) | ~1 h | none |
| G7 tests | ~45 min | none |
| G6 pagination (optional) | ~20 min | none |

**Recommendation:** ship **G1 + G7** together with key enablement (correctness + safety
first), then G2–G5 as a follow-up. Total ~2 h of code-only work. Adzuna is the cheapest
incremental India breadth available (real API, free key) — strong **P2** per the roadmap.

## 7. Risks
- **Low.** Official API, lawful, already-built, error-isolated. Main correctness risk is
  **G1** (region-only locations mis-tiered) — addressed by the ISO-suffix fix. Quota is
  the only operational watch-item, already mitigated by caching.

_No code, provider, or config was modified in producing this document._
