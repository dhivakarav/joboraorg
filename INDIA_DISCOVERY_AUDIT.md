# India-First Discovery — Audit & Fix

_Date: 2026-06-12. Investigated why India-first discovery still surfaces mostly
US roles (Notion, Ramp, Stripe). **Root cause: the only India-coverage provider
(JSearch) is disabled because no API key is configured — and nothing was loading
the documented `.env` anyway.** The ranking logic is correct; it simply has no
India jobs in the feed to lift._

## TL;DR
The India-first **ranking and filters work** — verified. But the live feed
contains **zero India jobs**, because every *active* provider is a US/EU board and
the one India provider (JSearch) is keyless → skipped. Notion = Lever, Ramp =
Lever, Stripe = Greenhouse — exactly what you're seeing. Fix = make `.env`
actually load + give you a ready slot for the free RapidAPI key.

## Check-by-check

### 1. Is `JSEARCH_API_KEY` configured?  ❌ NO
- No `.env` file existed at all (only `.env.example`, with an empty
  `JSEARCH_API_KEY=`).
- Not present in the shell environment either.
- → `os.getenv("JSEARCH_API_KEY")` returns `""`.

### 2. Is the JSearch provider active?  ❌ NO
`JSearchProvider.available()` is `bool(self.key)`, so with no key it returns
`False`. Live provider availability:

| Provider | Available | Region |
|---|---|---|
| Remotive | ✅ | Remote (mostly US/global) |
| Arbeitnow | ✅ | Europe |
| Greenhouse | ✅ | **US** ATS (Stripe, Airbnb, Coinbase, Databricks…) |
| Lever | ✅ | **US** ATS (**Notion**, **Ramp**, Brex, Spotify…) |
| Ashby | ✅ | **US** ATS |
| **JSearch** | **❌ (no key)** | **India + remote + internships** |
| Adzuna / Jooble / Workable / Internshala / Wellfound | ❌ (no key/feed) | — |

**Every active provider is US/EU.** `Notion`/`Ramp` come from `lever.py`'s board
list; `Stripe` from `greenhouse.py`'s. So the feed is structurally US-centric.

### 3. Is JSearch returning India jobs?  ❌ NO — it is never called
`aggregator._call_provider()` short-circuits with `return []` when
`not provider.available()`. JSearch is unavailable → it's never invoked → **0
India jobs enter the candidate set.**

### 4. Why does the badge still show "JSearch · Source Pending"?  ✅ Correct, by design
`provider_status()` reports `available: False` for JSearch (no key). The frontend
maps any provider in `PENDING_SOURCES` with `!available` to the yellow
"⏳ JSearch · Source Pending" badge. The badge is **accurately** reporting that
JSearch is off — it is a *symptom indicator*, not a bug.

### 5. Is India location ranking applied to live results?  ✅ YES — verified working
`_rank_key` runs on every result and **does** apply the India + priority-domain
bonus. Verified on a representative mixed feed:

```
Ranked order (rank_key | company | location):
   89.4  Razorpay   Bangalore, India      ← India hub + priority domain → top
   71.5  Stripe     Remote, US
   64.7  Notion     San Francisco, CA
```

So when an India job is present it sorts to the top correctly. **The ranking is
not the problem** — there are simply no India jobs to rank, because of #1–#3.

## Root cause
1. **No API key** for JSearch (the only India-coverage provider) → it's skipped.
2. **Secondary config bug:** the app read keys via `os.getenv` but **nothing
   loaded `.env`** — `python-dotenv` wasn't installed and there was no
   `--env-file`/loader. So even a correctly-filled `.env` would have been ignored.
   The documented `.env.example` workflow was silently non-functional.

## Fixes applied
| File | Fix |
|---|---|
| **`backend/app/config.py`** | Added a minimal, dependency-free `_load_dotenv()` that loads `backend/.env` or repo-root `.env` into `os.environ` at import (real env always wins; supports `#` comments + quotes). **Now a `.env` key actually enables the provider.** |
| **`.env`** (new, git-ignored) | Created with the India-first JSearch block + the empty `JSEARCH_API_KEY=` slot and step-by-step instructions to get the free RapidAPI key. |
| **`.env.example`** | Updated the stale JSearch section (correct India-first defaults, added `JSEARCH_DEFAULT_LOCATION`, signup URL, the "only India provider" warning). |

### Verified
- **Loader works end-to-end:** with a dummy key in `.env`, importing `app.main`
  → `JSearch.available() == True`, `default_location=India`, `country=in`,
  default query = `software engineer OR data scientist OR AI ML intern fresher`.
  (Dummy key reverted afterward.)
- **Ranking:** India hub + priority domain sorts first (table above).
- **Suite:** `pytest` → **65 passed** (no regressions from the config change).

## What YOU need to do to see India jobs (the one thing code can't do)
The API key is a credential only you can create:

1. Sign up free → https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
2. Subscribe to the **Basic** plan (free, 200 requests/month).
3. Copy your **X-RapidAPI-Key** into `JSEARCH_API_KEY=` in `/Users/dhivakarav/jobora/.env`.
4. Restart the backend.

Then: the "Source Pending" badge turns active, JSearch is called with
`country=in` + India location, and India roles enter the feed where the
(already-working) India + domain ranking lifts them to the top.

> **Honest note:** the free tier is 200 req/month. With provider + aggregate
> caching this is fine for personal/dev use, but it is the only legal India source
> wired in — broader India coverage (Internshala/Naukri/Foundit) still needs an
> authorized partner feed (see INDIA_PROVIDER_ROADMAP.md). No scraping was added.

---

## UPDATE (key provided) — second bug found & fixed
After the JSearch key was added to `.env`, JSearch fetched **real India jobs**
(verified: AI/ML internships in Mumbai, Hyderabad, Bengaluru, Chennai…), but **0
still reached the feed**. Root cause: a **location-matching bug** in
`app/jobs/base.py::matches_filters`.

- Google for Jobs / JSearch label Indian roles by **city + ISO country code** —
  `"Mumbai, Maharashtra, IN"`, `"Bengaluru, Karnataka, IN"`, or bare `"IN"` —
  **never the literal word "India".**
- The old filter did a plain substring test (`"india" in job_location`), so a
  `location=India` search **dropped every JSearch India job** before ranking.
  It also failed `Bangalore` ≠ `Bengaluru`.

**Fix:** India-aware location matching, centralized in `app/jobs/india.py`:
| Helper | Purpose |
|---|---|
| `_is_india()` | recognizes the `", IN"` suffix + bare `"IN"` + all hubs |
| `is_india_filter()` / `india_location_matches()` | India/Remote-India/city filters with synonyms (Bangalore↔Bengaluru, Delhi NCR group) |
| `india_bonus()` / `is_india_location()` | now use `_is_india`, so `", IN"` roles also get the ranking boost |
| `base.py::matches_filters` | uses the India-aware matcher for India filters |

**Verified end-to-end (live key, real HTTP endpoint):**
`GET /api/jobs?q=AI ML intern&location=India` → **10 results, all JSearch India
AI/ML internships** (Chennai, Coimbatore, Mumbai, Nagpur…), US boards correctly
filtered out, JSearch badge now **active**. Added 6 regression tests for the
`", IN"` suffix + city aliases. Suite: **71 passed** (was 65).

> **Config note:** the live key is in `/Users/dhivakarav/jobora/.env` (git-ignored).
> Tests force `JSEARCH_API_KEY=""` in `conftest.py`, so the suite never consumes
> the live quota.
