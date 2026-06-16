# Internshala — Phase 1 (Discovery only, NO auto-submission)

## TL;DR — the blocker you must know first
Internshala has **no official public jobs API**, and its **`robots.txt` disallows**
exactly the discovery paths (`/internship/search/`, `/job/search/`,
`/internship/details/`, `/job/details/`, `/api/`, and any `?query` URL). So a
lawful, robots-compliant scraping integration is **not possible**, and Jobara
does **not** scrape it or fabricate listings.

Phase 1 therefore ships the **complete internship discovery pipeline + a
robots-gated provider seam** that activates the moment an **authorized data
source** is configured (official API / partner feed / licensed dataset). With no
authorized source, the Internshala provider is reported **unavailable** and
returns nothing — by design and honestly.

Everything requested works through the existing pipeline once a source exists:
internship/fresher/remote listings, match scoring, **INR stipend display**,
duplicate detection, and activity tracking. **No auto-submission** (the
Internshala adapter is manual-only).

---

## Architecture

```
 Authorized source (env: INTERNSHALA_FEED_URL)        ┌─ NOT used: scraping ─┐
 official API / partner / licensed JSON feed          │ robots.txt disallows │
              │                                        │ search/detail/api    │
              ▼                                        └──────────────────────┘
 InternshalaProvider.fetch()
   ├── available() == bool(INTERNSHALA_FEED_URL)      # disabled if unset
   ├── robots.can_fetch(feed_url)  (unless INTERNSHALA_FEED_TRUSTED=1)
   └── map each record → RawJob(employment_type, stipend→salary, duration, remote)
              │
              ▼
 aggregator.search(..., employment_type=)             # existing fan-out
   ├── matches_filters(query, location, keywords, employment_type)
   ├── salary_to_inr_sync(stipend)                     # INR stipend display
   ├── dedupe by RawJob.fingerprint                    # duplicate detection
   └── cache (Redis/memory, TTL)
              │
              ▼
 GET /api/jobs?employment_type=internship             # discovery API
   ├── score_job(profile)                              # match scoring
   └── adapter_for(job) → InternshalaAdapter           # manual_only (no submit)
              │
              ▼
 POST /api/jobs/apply (Save/Applied)                   # activity tracking
   └── Application row (salary_inr, status) → Activity Log
```

**Design principle (unchanged):** official APIs preferred; scraping only where
`robots.txt` permits; never fabricate listings. Internshala fails the scraping
test, so it's gated behind an authorized feed.

## Data model changes
Minimal and additive — internships reuse the existing `RawJob`/`Application`
pipeline (so INR stipend, dedupe, tracking all work for free):

- **`RawJob`** (`app/jobs/base.py`) + **`JobOut`** (`schemas.py`): added
  - `employment_type` — `"internship" | "fresher" | "job" | ""`
  - `duration` — e.g. `"3 months"`
  - (stipend maps to the existing `salary` → `salary_inr` via FX conversion)
- **No new tables.** Tracking uses the existing `Application` model
  (`salary_inr`, `status`, `manual_required`, dedupe via `job_url_hash`).
- **No migration required** for discovery (the new fields are on the in-memory
  job/search models, not persisted columns). If you later want to persist
  `employment_type` on tracked applications, that's a one-column migration.

## API endpoints
- **`GET /api/jobs?employment_type=internship|fresher|job|any`** — discovery,
  now filterable by employment type (plus existing `q`, `location`, `limit`,
  `refresh`). Returns `employment_type`, `duration`, `salary_inr`, `match_score`,
  `platform`, `manual_required`, `applied` per job.
- **`GET /api/jobs/sources`** — now lists `Internshala` with
  `available=false`, `requires_key=true`, `official_api=false` (and the reason
  is exposed by the provider) so the UI can show "configure an authorized
  source".
- **`POST /api/jobs/apply`** — existing Save/Applied tracking; Internshala jobs
  route to the manual-only adapter (no auto-submit endpoint exists for them).
- **No Internshala submit endpoint** — by requirement.

## What's verified (automated tests — `tests/test_internshala.py`, 6 passing)
- Provider is **disabled** without an authorized source; `available()==False`
  and the reason cites robots.txt / no API.
- Feed record → `RawJob`: `employment_type=internship`, `duration`,
  `remote` (Work-From-Home → remote), **`salary_inr` populated** from stipend.
- Fresher classification (`"Fresher Job"` → `fresher`).
- **Dedupe**: same record id → identical fingerprint.
- **employment_type filter**: internship-only excludes jobs; `any` passes all.
- **Adapter is manual-only**: `Internshala` → `manual_only=True`,
  `auto_submit=False`.
(Full suite: **21 passing**.)

> The feed-record sample in the test is the *documented feed contract* for a unit
> test — not scraped or fabricated production data.

---

## Production Readiness Report — Internshala Phase 1

| Area | Status |
|---|---|
| Discovery pipeline (match/INR/dedupe/tracking) | ✅ Implemented + tested |
| Internship / fresher / remote categorization + filter | ✅ `employment_type` + `remote` |
| INR stipend display | ✅ via FX conversion (`salary_inr`) |
| Auto-submission | ⛔ Intentionally absent (manual-only adapter) |
| **Live data source** | ❌ **Blocked** — no public API; robots.txt disallows scraping |
| robots.txt compliance | ✅ Provider is robots-gated; disallowed paths never fetched |
| Fabricated data | ✅ None — provider returns empty without an authorized source |

### The gating finding (must resolve before Internshala discovery is usable)
There is currently **no lawful way to obtain Internshala listings** in real time:
- **No official public API** for jobs/internships.
- **robots.txt disallows** `/internship/search/`, `/job/search/`,
  `/internship/details/`, `/job/details/`, `/api/`, and `?query` URLs.
- Internshala additionally blocks AI/LLM crawlers (incl. Anthropic/Claude) at the
  domain level.

**Lawful paths to enable it (pick one, then set `INTERNSHALA_FEED_URL`):**
1. **Internshala partnership / official API or affiliate feed** (best — durable,
   ToS-clean). Many job platforms offer partner/affiliate data access.
2. **A licensed third-party dataset / job-data aggregator** that includes
   Internshala listings under license.
3. If Internshala ever exposes a permitted feed/sitemap with listing data, point
   the provider at it (the robots gate will enforce permission per-URL).

Until one is in place, keep Internshala **off** (current default) and surface it
in the UI as "coming soon / source pending" rather than showing empty results.

### Recommendation
- **Do not** enable Internshala discovery by scraping — it's disallowed and would
  put user trust + legal standing at risk (and contradicts the integrity stance
  the whole product is built on).
- **Do** pursue an authorized feed; the integration seam is built and tested, so
  enabling it is a config + field-mapping task (the provider's `_to_rawjob`
  already maps the documented shape), not new architecture.
- Phase 2 (auto-apply) is **not** on the table for Internshala: it's account-gated
  and automation-restricted — manual-apply is the correct, honest end state.
