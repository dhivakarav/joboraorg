# India-First Job Discovery (JSearch) — Implementation Report

_Date: 2026-06-12. Implemented against the existing JSearch provider. No new job
boards added, no scraping, no changes to the Greenhouse / Lever / Ashby apply
pipelines, no deploy, no payments._

## Goal
Improve Indian job discovery for students/freshers using the **existing** JSearch
(Google for Jobs via RapidAPI) provider — India-first, internship/fresher-first,
priority-domain-first, with company / location / salary / duration filters and
better ranking.

## What changed (5 files, +1 new module, +1 test file)

### Backend
| File | Change |
|---|---|
| **`app/jobs/india.py`** (new) | Pure, testable India-first signals + filters: `india_bonus`, `domain_bonus`, `is_india_location`, `company_match`, `salary_inr_annual`, `passes_salary`, `duration_match`. No network. |
| **`app/jobs/providers/jsearch.py`** | India-first defaults: location-less searches now anchor to **India** (`default_location`, `country=in` always sent); default query upgraded to a priority-domain blend (`software engineer OR data scientist OR AI ML intern fresher`). |
| **`app/routers/jobs.py`** | (a) `_rank_key` now adds an **India-location bonus** + **priority-domain bonus** on top of eligibility/match. (b) `GET /api/jobs` gains `company`, `min_salary`, `duration` query params with post-eligibility filtering. (c) analytics captures the new filters. |

### Frontend
| File | Change |
|---|---|
| **`pages/user/FindJobs.jsx`** | India-first **Location** list (India, Remote India, Chennai, Bangalore, Hyderabad, Pune, Mumbai, Delhi NCR, Remote); new **Company** text filter, **Min salary** select (₹3/6/10/15 LPA+), **Internship duration** select (2/3/6 months); all wired into `load()`. |

### Tests
- **`tests/test_india.py`** (new, 17 tests): pure helpers (salary parsing, India/domain
  bonuses, company/duration/salary matchers) + endpoint tests for the company,
  min-salary, duration filters and India+domain ranking order.

## Requirements coverage
| # | Requirement | Status | How |
|---|---|---|---|
| 1 | Prioritize India jobs | ✅ | JSearch `country=in` + India default location; `india_bonus` in ranking (hub > remote > none). |
| 2 | Prioritize internships & fresher roles | ✅ | Existing `early_signal` hard filter (default ON for students/freshers) + JSearch default query. |
| 3 | Prioritize AI/ML, SWE, Data Scientist, Backend, Full Stack | ✅ | `domain_bonus` ranking boost on those titles; JSearch default query. |
| 4 | Hide senior roles by default | ✅ | Existing eligibility filter (senior/staff/principal/lead/manager/PhD/3+ yrs hidden for early-career). |
| 5 | Company filters | ✅ **new** | `?company=` (case-insensitive substring) + UI field. |
| 6 | Location filters (Chennai/Bangalore/Hyderabad/Pune/Remote India) | ✅ **new** | India-first `LOCATIONS` list folded into the JSearch query. |
| 7 | Salary filters | ✅ **new** | `?min_salary=` (annual INR) + UI buckets; unknown-salary roles kept. |
| 8 | Internship duration filters | ✅ **new** | `?duration=` + UI buckets; unknown-duration roles kept (see caveat). |
| 9 | Improved ranking for Indian students | ✅ | `_rank_key` = eligibility·0.55 + match·0.30 + India bonus + domain bonus. |

## Honest caveats
- **Salary & duration data are sparse** from aggregators. Both filters deliberately
  **keep unknown-value roles** rather than hide them (most internships publish
  neither) — so they narrow results without nuking the feed. Duration filtering only
  excludes a role when it *declares* a non-matching duration.
- **JSearch stays gated**: it returns nothing until `JSEARCH_API_KEY` is set (free
  RapidAPI Basic = 200 req/month). All ranking/filter logic above is live regardless
  of provider, so it also improves the other providers' India results.
- Salary parsing (`salary_inr_annual`) is best-effort (handles ₹/L/Cr/k and monthly
  annualization, takes the first figure of a range).

## Verification
- **Backend:** `pytest` → **65 passed** (was 48; +17 new India tests).
- **Frontend:** `npm run build` → clean (60 modules, built in ~0.8s).
- **No changes** to Greenhouse/Lever/Ashby submit pipelines, status/evidence model,
  or any apply flow. No deploy, no payments.
