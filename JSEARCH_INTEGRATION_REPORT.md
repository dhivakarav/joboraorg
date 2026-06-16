# JSearch Integration Report

Integrated **JSearch (RapidAPI → Google for Jobs)** as a new discovery provider —
official API only, no scraping. Greenhouse / Lever / Ashby pipelines untouched; no
deploy, no payments.

## 1. Provider adapter (existing architecture)
`app/jobs/providers/jsearch.py` → `JSearchProvider(Provider)`, mirroring the keyed
provider pattern (Adzuna/Jooble):
- `name = "JSearch"`, `requires_key = True`, `official_api = True`.
- `available()` → `bool(JSEARCH_API_KEY)` — **gated**: returns nothing until a key
  is set (verified: `available: False` in `provider_status` with no key).
- Registered in `app/jobs/providers/__init__.py` → `ALL_PROVIDERS`.
- Maps the JSearch response → `RawJob` (title, company, apply_url, location,
  salary, remote, posted_at, employment_type, description, `jsearch-{job_id}`),
  drops URL-less rows, and **isolates errors** (a failure yields `[]`, never raises).

## 2. Official API only / 3. No scraping
- Single documented endpoint: `https://jsearch.p.rapidapi.com/search`.
- Authenticated with `X-RapidAPI-Key` + `X-RapidAPI-Host` headers (a free RapidAPI
  key). No HTML scraping, no robots-restricted paths — JSearch is a licensed
  Google-for-Jobs aggregator. (A test asserts the endpoint + auth headers.)

## 4. Internships / entry-level / remote
- `job_employment_type` containing `INTERN` → `employment_type = "internship"`;
  other types fall to title inference (fresher vs job).
- `job_is_remote` → `RawJob.remote`.
- The provider does **not** over-filter — it returns intern/entry/remote roles so
  Jobora's own ranking/filters decide visibility.

## 5. Eligibility scoring / 6. Internship-&-new-grad filter (automatic)
JSearch jobs flow through the same pipeline as every provider — no special-casing:
- `jobs._decorate` runs `eligibility()` + `early_signal()` on each JSearch row.
- Verified by test: a JSearch "Software Engineer Intern" → `eligible: True`,
  tier ∈ {Excellent, Good}, and `early_signal == "Internship"` (so it **survives
  the internships-only hard filter** and ranks for students).

## 7. Tracking flow (automatic, pipelines untouched)
JSearch apply links vary by employer (`company_domain` left empty), so they route
to the **generic adapter → "Track & Apply on Company Site"**: clicking Apply opens
the official page and records a **Tracked** event via `/api/jobs/apply`. No
Greenhouse/Lever/Ashby code touched.

## 8. Provider badge "JSearch"
- Appears in `aggregator.provider_status()` → the Find Jobs **Sources** row shows
  `JSearch` (green ● when keyed, ○ when not).
- Added to the frontend `PENDING_SOURCES` map → when unconfigured it shows a
  **"⏳ JSearch · Source Pending"** badge with a tooltip explaining a free RapidAPI
  key is needed.
- Each JSearch job card shows the `🔗 JSearch` source meta.

## 9. Tests — `tests/test_jsearch.py` (4, all passing)
- gating (`available()` false→true on key);
- official-API mapping (RapidAPI headers, endpoint, query incl. location) +
  field mapping (internship, remote, India location, salary, id);
- error isolation (network failure → `[]`);
- registration + eligibility/early-signal integration.

Suite: **40 → 44 passing.** Frontend build clean.

## Configuration (gated; off by default)
`.env.example` documents:
```
JSEARCH_API_KEY=            # free RapidAPI key → enables JSearch
JSEARCH_HOST=jsearch.p.rapidapi.com
JSEARCH_COUNTRY=in          # India-relevant default when no explicit location
JSEARCH_DEFAULT_QUERY=      # optional; defaults to "software developer intern"
```
With no key, JSearch is inert (returns nothing, shows Source Pending) — nothing
else changes.

## Compliance
Licensed aggregator API; no scraping, no robots-restricted access, no OAuth/user
credentials. Honor RapidAPI's free-tier **rate limits** — Jobora's existing
provider-level + aggregate caching already minimizes calls (JSearch is
query-keyed, not query-agnostic).

## Verification status
- ✅ Code, gating, mapping, eligibility/filter/tracking integration, tests, build.
- ⏳ **Live data not fetched** here (no RapidAPI key in this environment — by
  design). To verify end-to-end: set `JSEARCH_API_KEY` and search Find Jobs; the
  source flips to ●, and India/remote/intern results appear ranked by eligibility.

## Result
JSearch is implemented, gated, tested, and wired into discovery + eligibility +
the internship filter + Track & Apply — the highest-impact source from
`PROVIDER_EXPANSION_REPORT.md` for India + internship coverage — without touching
the existing ATS pipelines.
