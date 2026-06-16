# Adzuna Integration — Verification Report

_Date: 2026-06-16. Implemented + verified. Provider/ranking code only; no apply-flow
changes._

## Summary
The Adzuna provider is **implemented, India-tier-correct, and tested**. India detection
(the design's must-fix **G1**) is fixed and proven against the four required location
scenarios. **Live job discovery requires a free Adzuna key** — the provider is correctly
gated `available()=False` until `ADZUNA_APP_ID` + `ADZUNA_APP_KEY` are set (exactly like
JSearch was before its key). Code-verified capability is reported below; live volume
metrics are pending the key.

## What changed
| File | Change |
|---|---|
| `app/jobs/providers/adzuna.py` | **India detection fix:** for `country=in`, results whose Adzuna label is a region/state ("Karnataka"), bare city, or blank are tagged `", India"` so the India-first tier function classifies them Tier 1/2 (not global). Added **remote inference** (`_REMOTE_RE` over title/location/description), **employment-type inference** (`infer_employment_type` → internship/fresher/job), and **INR salary labelling** for `in`. |
| `.env` | Added `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` scaffold + enable instructions. |
| `tests/test_adzuna.py` | 9 regression tests (mocked, no network/key). |

## Requirements coverage
| # | Requirement | Status |
|---|---|---|
| 1 | Enable the existing Adzuna provider | ⚠️ Code enabled + gated; **needs a free key to go live** (scaffold added) |
| 2 | India detection (country=IN, Karnataka/India/Bengaluru, Remote India) | ✅ Fixed + tested |
| 3 | Regression tests: India onsite / India remote / US remote / Europe onsite | ✅ All 4 + more |
| 4 | India-tier ranking works with Adzuna jobs | ✅ Tested (India floats to top) |
| 5 | Backend tests + frontend build | ✅ 89 passed / build clean |
| 6 | This report | ✅ |

## Verification evidence (code-level, mocked — real test results)

### India detection (Requirement 2) — the 4 scenarios
| Scenario | Input (Adzuna) | Result | Tier |
|---|---|---|---|
| **India onsite (region only)** | `country=in`, "Karnataka" | tagged "Karnataka, India" | **Tier 1** ✅ |
| India onsite (city/country/blank) | `in`, "Bengaluru" / "India" / "" | all India | **Tier 1** ✅ |
| **India remote** | `in`, "Remote Software Engineer", "Bengaluru" | remote=True | **Tier 2** ✅ |
| **US remote** | `us`, "Remote Backend Engineer", "San Francisco, CA" | remote=True | **Tier 3** ✅ |
| **Europe onsite** | `de`, "Software Engineer", "Berlin, Germany" | remote=False | **Tier 3** ✅ |

### India-tier ranking with Adzuna jobs (Requirement 4)
Mixed Adzuna feed (US + EU + India, India listed last) → sorted by tier →
**`Infosys` (India) floats to the top**, global jobs sink to the bottom. ✅

### Tests
- `tests/test_adzuna.py` → **9 passed**: gating, official-payload mapping, the 4
  location scenarios, internship/fresher inference, and India-first ranking.
- Full suite → **89 passed** (was 80; +9). No regressions.
- `npm run build` → clean.

## Coverage analysis

> **Capability is verified now; live volume needs the key.** With a key set, Adzuna
> queries India (`in`) — every `in` result is guaranteed India-tagged (Tier 1/2) by the
> G1 fix, so **India coverage of Adzuna's `in` feed = 100% correctly tiered**.

| Metric | Status |
|---|---|
| **Jobs discovered (live count)** | ⏳ Pending key — provider returns 0 until `ADZUNA_APP_ID`/`KEY` set |
| **India coverage** | ✅ Capability: all `country=in` results tiered India (1/2), incl. region-only labels. Live % pending key. |
| **Internship coverage** | ✅ Title inference tags internships (`"…Intern"` → `internship`). Live volume pending key. |
| **Fresher coverage** | ✅ Title inference tags fresher (`"Graduate Engineer Trainee"`, "trainee", "new grad" → `fresher`). Live volume pending key. |

## API usage limits
- Adzuna requires a **free developer registration** (App ID + App Key) from
  `developer.adzuna.com`. The free tier has **documented per-minute / per-day call caps**
  (confirm current values on the developer portal — they change).
- **Mitigations already in place:** provider-level + aggregate response caching
  (`JOB_CACHE_TTL`) and `PROVIDER_MIN_INTERVAL` throttling, so repeated/identical searches
  do not spend calls. Failures are isolated (`_fetch_country` returns `[]` on error) — an
  Adzuna outage or quota exhaustion never breaks search.
- *Recommended follow-up:* a shared monthly request counter + admin "quota low" signal
  (same util proposed for JSearch).

## Maintenance cost — LOW
- **Official, documented REST API** (not scraping) → stable, lawful, low churn.
- Error-isolated and gated; dormant (returns nothing) until configured — no dead code.
- Field mapping is small and centralized; the India tier logic is shared (`india.py`),
  so no Adzuna-specific ranking to maintain.

## To go live (operator step — the one thing code can't do)
1. Register free at **https://developer.adzuna.com** → App ID + App Key.
2. Paste both into `/Users/dhivakarav/jobora/.env` (`ADZUNA_APP_ID`, `ADZUNA_APP_KEY`).
3. Restart the backend → "Adzuna · Source Pending" clears; India results tier correctly.

If you provide a key (as you did for JSearch), I can run a live discovery pass and fill in
the real jobs-discovered / coverage numbers.

_No apply-flow, Greenhouse/Lever/Ashby, or unrelated code was modified._
