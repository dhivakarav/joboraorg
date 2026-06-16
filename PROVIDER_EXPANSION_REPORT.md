# Provider Expansion Report — Next 10 Legal, Scraping-Free Job Sources

_Research only. No deploy, no payments. Date: 2026-06-12._

## Method & exclusions
Goal: rank the next sources to integrate for Jobora's audience (students /
freshers / internships, **India-relevant + remote**). Each candidate was checked
for a **documented public API or official feed** and a permissive **robots.txt**
(API/feed paths reachable, not disallowed). Reachability was verified live
(HTTP status). **Excluded:** Internshala; anything requiring scraping; anything
robots-blocked; anything with no legal integration path — which rules out
**Indeed** (publisher API closed to new partners), **LinkedIn** (partner-only, no
open jobs API), **Naukri** (no public API, scraping disallowed), **Glassdoor**
(API deprecated), and dead APIs (GitHub Jobs, SO Jobs). Already-integrated sources
(Remotive, Arbeitnow, Greenhouse, Lever, Ashby, Adzuna, Jooble) are not re-listed.

Verified live this run: The Muse `200`, Jobicy `200`, RemoteOK `200`,
WeWorkRemotely RSS `200`, HN Algolia `200`, SmartRecruiters postings `200`,
USAJOBS `401` (needs free key; reachable), Careerjet `403` (needs free affiliate
id). robots.txt for RemoteOK / WeWorkRemotely / Jobicy **allow** their API/feed.

## Scoring
Priority /100 = India (30) + Internship/early-career (25) + Remote (15) +
Free & low-friction (15) + Legal certainty / no-OAuth (15).

---

## The 10 candidates
| # | Source | Public API? | Free tier? | Internship coverage | India coverage | Remote coverage | OAuth req? | Effort | Priority |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **JSearch (RapidAPI → Google for Jobs)** | ✅ Yes | ✅ (free tier, key) | ✅ High (intern/fresher) | ✅ **High** | ✅ High | No (API key) | Low–Med (~1d) | **92** |
| 2 | **SmartRecruiters Posting API** | ✅ Yes (per-company, like Greenhouse) | ✅ (no key) | ⚠️ Some | ⚠️ Some (global employers) | ⚠️ Some | **No** | **Low (~0.5–1d)** | **84** |
| 3 | **The Muse API** | ✅ Yes | ✅ (key, generous) | ✅ Good (levels incl. internship/entry) | ⚠️ Some | ✅ Good | No (API key) | Low (~1d) | **80** |
| 4 | **Careerjet API** | ✅ Yes (affiliate) | ✅ (free affiliate id) | ✅ Good | ✅ **High** (in.careerjet) | ⚠️ Some | No (affiliate key) | Low–Med (~1d) | **79** |
| 5 | **Jobicy API** | ✅ Yes | ✅ (no key) | ✅ Good (entry/intern remote) | ⚠️ Remote-global | ✅ **High** | **No** | **Low (~0.5d)** | **74** |
| 6 | **RemoteOK API** | ✅ Yes (`/api`, attribution) | ✅ (no key) | ⚠️ Some | ⚠️ Remote-global | ✅ **High** | No | Low (~0.5d) | **68** |
| 7 | **WeWorkRemotely RSS** | ✅ Official RSS | ✅ (no key) | ⚠️ Some | ⚠️ Remote-global | ✅ **High** | No | Low (~0.5d) | **64** |
| 8 | **Recruitee / Teamtailor public ATS APIs** | ✅ Yes (per-company) | ✅ (no key) | ⚠️ Some | ⚠️ Mostly EU | ⚠️ Some | No | Med (per-company config, like Lever) | **58** |
| 9 | **USAJOBS API** | ✅ Yes (gov) | ✅ (free key) | ✅ High (Pathways/Interns) | ❌ **None (US-only)** | ⚠️ Some | No (API key + Host) | Low (~1d) | **45** |
| 10 | **HN "Who is hiring" via Algolia API** | ✅ Yes (HN Algolia, public) | ✅ (no key) | ⚠️ Low | ⚠️ Some | ✅ High (startups) | No | Med (parse thread → roles) | **42** |

> All 10 require **no OAuth** (public, API-key, or affiliate-id auth) and have a
> **legal API/feed** with permissive robots. Effort assumes mapping the feed →
> `RawJob` and reusing the existing eligibility / matching / dedupe / INR pipeline.

---

## Top 5 to implement next (ranked)

### 1. JSearch (RapidAPI / Google for Jobs) — **highest impact**
The single biggest win for Jobora's India + internship audience: a licensed
aggregator that surfaces Google-for-Jobs results (incl. many India + remote
intern/fresher roles) through one clean API. Free RapidAPI tier (rate-limited);
upgrade later if needed. **Effort ~1d.** Caveat: rate limits on the free tier —
cache aggressively (Jobora already does provider-level caching).

### 2. SmartRecruiters Posting API — **fastest, zero-key**
Mirrors the proven Greenhouse/Lever/Ashby ATS pattern: public per-company posting
API, **no key**, official. Adds real employer listings (some India/remote/intern)
with the least new plumbing. **Effort ~0.5–1d.** Curate a company list via env
(like `GREENHOUSE_BOARDS`).

### 3. The Muse API — **clean internship + remote coverage**
Documented public API with explicit experience **levels** (internship/entry),
remote flags, and company data — well-suited to the student filter. Free key.
**Effort ~1d.**

### 4. Careerjet API — **India breadth**
Free affiliate API with strong **India** coverage (in.careerjet) and intern/fresher
roles — complements JSearch for density in the target geography. Requires a free
affiliate id + attribution. **Effort ~1d.**

### 5. Jobicy API — **easy remote density**
Zero-key remote-jobs API with entry-level/intern remote roles; trivial to add and
boosts result density for the internship filter. **Effort ~0.5d.**

---

## Compliance notes
- Every listed source exposes a **documented API or official RSS** and has a
  **robots.txt that permits** that endpoint — **no scraping** is involved.
- **Attribution/ToS to honor:** RemoteOK (link-back attribution), Careerjet
  (affiliate-id + result attribution), JSearch/RapidAPI (per their terms +
  rate limits). Implement these per each provider's terms.
- **No OAuth or user-credential handling** for any of the 10 — they are read-only
  discovery sources; apply remains via the existing Track & Apply / Assisted Apply
  flows (unchanged).
- **Keyed providers stay gated** (the Workable/Adzuna/Jooble pattern): a source is
  `available() == False` until its key/affiliate-id is configured, so nothing
  breaks when unconfigured.

## Recommended sequence
**Sprint A (1–2 days, biggest reach):** JSearch + SmartRecruiters.
**Sprint B (1–2 days, India + remote density):** Careerjet + The Muse + Jobicy.
This adds **India breadth** (JSearch, Careerjet) and **internship/remote density**
(The Muse, Jobicy, SmartRecruiters) — directly addressing the result-sparsity
finding from the product audit — all without scraping and reusing Jobora's
existing provider seam, eligibility ranking, and Track/Assisted apply flows.

## Sources
Live endpoint checks (this run): `themuse.com/api/public/jobs`,
`jobicy.com/api/v2/remote-jobs`, `remoteok.com/api`,
`weworkremotely.com/remote-jobs.rss`, `hn.algolia.com/api/v1/search`,
`data.usajobs.gov/api/search`, `api.smartrecruiters.com/v1/companies/{co}/postings`,
`public.api.careerjet.net/search`; robots.txt for remoteok.com / weworkremotely.com /
jobicy.com. Excluded per no-legal-path: Indeed Publisher (closed), LinkedIn
(partner-only), Naukri (no API), Glassdoor (deprecated).
