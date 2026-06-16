# India-First Discovery v2 — Design & Implementation Plan

_Date: 2026-06-16. **Plan only — no code changed.** Grounded in live verification
against the running stack. Covers: JSearch status, India-first ranking, Wellfound,
Internshala feasibility, and a ranked provider roadmap._

---

## 1. Verify JSearch is fully active ✅ ACTIVE

| Check | Result |
|---|---|
| Key loaded (`.env` → `_load_dotenv`) | ✅ `82501f…f175` |
| `JSearchProvider.available()` | ✅ `True` |
| Country / default location | `country=in`, `default_location=India` |
| Live API call (earlier this session) | ✅ Returned 10 real India jobs (Google SE Intern–Hyderabad, Novetum–Hyderabad, Teckat–Ranchi…) |
| Live `/api/jobs/sources` on running server | ✅ `JSearch available=True` (no longer "Source Pending") |

**Status: fully active.** One caveat to track — **free tier = 200 req/month**; each
uncached (query, location) pair spends one request. Mitigations already in place:
provider-level + aggregate caching (`JOB_CACHE_TTL`). *Plan item:* add a lightweight
monthly request counter + a "JSearch quota low" admin signal (see roadmap §5).

---

## 2. Ensure India jobs rank above US/EU

### Current behavior (verified)
`_rank_key` = `eligibility*0.55 + match*0.30 + india_bonus(loc,remote) + domain_bonus(title)`,
where `india_bonus` = **+25** (India hub) / **+8** (generic remote) / **0** (US/EU onsite).

Live test, equal eligibility(98)/match(50), no location filter:
```
108.9  Razorpay   Bengaluru, India     ← India hub
108.9  GitLabIN   Remote, India        ← India tag
 91.9  NotionUS   Remote, US           ← remote +8
 83.9  Stripe     San Francisco, CA    ← US onsite +0
 83.9  TecFox     Berlin, Germany      ← EU onsite +0
```
✅ India ranks above US/EU **when scores are comparable.**

### Gap
The bonus is a **flat additive**, so a US role with a much higher match/eligibility
can still outrank an India role. Example: US (elig 98, match 80, remote) →
`53.9+24+8 = 85.9`; India (elig 70, match 30) → `38.5+9+25 = 72.5` → **US wins**.
For a *guaranteed* India-first ordering this is insufficient.

### Design options (pick one)
| Option | Change | Pros | Cons |
|---|---|---|---|
| **A. India primary sort tier (recommended)** | Sort key = `(is_india_or_remote_india DESC, _rank_key DESC)`. India bucket always precedes non-India; existing score orders within each bucket. | Hard guarantee India-first; relevance preserved inside the bucket; ~5 lines | Pushes a perfect US match below a weak India role (intended for India-first) |
| **B. Proportional/large bonus** | Raise India hub bonus to e.g. +60, or make it `+0.6*base` | Simple knob | Still not a hard guarantee; magic number; harder to reason about |
| **C. Location-default to India** | Default `location="India"` in the API/UI so US is filtered out entirely | Strongest (US never enters feed) | Hides remote-global roles a student might want; already a separate frontend gap (dropdown doesn't re-query — see §note) |

**Recommendation: Option A** (tiered sort) + keep the existing bonuses for in-bucket
ordering. Optionally combine with C as the *default* while letting the user widen.

### Implementation plan (Option A)
- File: `app/routers/jobs.py` → replace `items.sort(key=_rank_key, reverse=True)` with a
  two-key sort: primary `india.is_india_location(j.location, j.remote)` (desc),
  secondary `_rank_key` (desc). One helper already exists (`india.is_india_location`).
- Add a `JobSearchOut` field `india_first: bool` (telemetry/debug).
- Tests: extend `tests/test_india.py` — assert a low-match India role still outranks a
  high-match US role; assert in-bucket order still follows `_rank_key`.
- Effort: ~30 min, no provider/aggregator changes.

> **Note (separate, already documented):** the frontend Location dropdown doesn't
> re-query on change (`FindJobs.jsx`), so India-first only applies after clicking
> Search. That UX fix is tracked in the earlier audit and is orthogonal to ranking.

---

## 3. Add Wellfound as a provider

### Reality check (verified against the existing stub + robots)
`app/jobs/providers/wellfound.py` **already exists** as a robots-gated seam:
- Wellfound (AngelList Talent) has **no public jobs API**.
- Its `robots.txt` **disallows** the job paths (`/_jobs/`, `?jobId`, `?jobSlug`, `/role/…`).
- Job data sits behind an **authenticated GraphQL** endpoint.
- The provider `available()` returns `False` until `WELLFOUND_FEED_URL` (a licensed/
  partner feed) is configured; every fetch is additionally `can_fetch()` robots-gated.

**So "adding Wellfound" cannot mean scraping** — that's unlawful (robots/ToS) and the
project forbids it. It means wiring an **authorized data source** into the existing seam.

### Implementation plan (authorized-feed path)
1. **Obtain an authorized source** (the only lawful options):
   - Wellfound partner/affiliate feed, **or**
   - a licensed job dataset that includes Wellfound postings, **or**
   - Wellfound's official employer/partner API if granted access.
2. **Configure** `WELLFOUND_FEED_URL` (+ `WELLFOUND_FEED_TRUSTED=1` if the host isn't
   wellfound.com). The seam then activates automatically (no code change needed).
3. **Field mapping** — already scaffolded in `fetch()` (title, company/startup,
   apply_url/url, location, salary/compensation, remote, intern→employment_type). Verify
   against the real feed shape; add India detection via the existing `india._is_india`
   on the feed's location string.
4. **India relevance** — Wellfound skews US startups; expect modest India coverage.
   Plan: pass `location=India` through to the feed query if the feed supports it.
5. **Tests** — add `tests/test_wellfound.py` mirroring `test_jsearch.py` with a mocked
   feed client (no network); assert gating (unavailable without `FEED_URL`), mapping,
   and India tagging.
6. **Effort:** ~1–2 h once a feed exists; **0 without a feed** (it stays a dormant seam).

**Verdict:** no engineering blocker — the seam is ready. The blocker is **acquiring a
licensed feed**. Until then, "Wellfound" remains correctly shown as *Source Pending*.

---

## 4. Internshala integration — feasibility

### Verified reality
`app/jobs/providers/internshala.py` exists as the same kind of **lawful seam**:
- **No official public jobs API.**
- `internshala.com/robots.txt` **disallows** `/internship/search/`, `/job/search/`,
  `/internship/details/`, `/job/details/`, `/api/`, and any `?query` URL.
- Scraping these violates robots + ToS → **not done**, no fabricated listings.
- Activates only via `INTERNSHALA_FEED_URL` (official API / affiliate / licensed dataset),
  robots-gated per fetch.

### Feasibility verdict
| Path | Feasible? | Notes |
|---|---|---|
| Scrape search/listing pages | ❌ No | robots-disallowed + ToS; project policy forbids |
| Official public API | ❌ None exists | Internshala publishes none for candidates |
| **Affiliate / partner feed** | ⚠️ Conditional | Internshala runs an affiliate program; a data/partner feed would be the lawful unlock. Requires a business agreement. |
| Licensed aggregator that includes Internshala | ⚠️ Conditional | e.g. a paid dataset; cost vs. value tradeoff |
| **JSearch as interim proxy** | ✅ Already live | Google for Jobs already surfaces many Internshala-style India internships via JSearch — covers much of the need today |

**Conclusion:** Direct Internshala integration is **blocked on a partnership/feed**, not on
engineering — the seam is built and waiting for `INTERNSHALA_FEED_URL`. **Highest-value
near-term action is to lean on JSearch** (already active) for India internship coverage,
and pursue the Internshala affiliate/partner feed as a parallel business track. Full prior
analysis: `INTERNSHALA_FEASIBILITY_REPORT.md`, `INDIA_PROVIDER_ROADMAP.md`.

---

## 5. Provider roadmap — ranked

Scored 1–5 (5 = best) on each axis. **Priority** weights India + internship coverage
highest (the product's purpose), then automation feasibility, then maintenance cost.

| Provider | India cov. | Internship cov. | Automation feasibility | Maintenance cost (5=cheap) | Status | Priority |
|---|:--:|:--:|:--:|:--:|---|:--:|
| **JSearch** (Google for Jobs) | 5 | 5 | 4 (live API, keyed) | 3 (200/mo quota, query-shaped) | ✅ Active | **P0 — done; harden** |
| **Greenhouse** | 3 | 3 | 5 (read API + gated submit) | 4 | ✅ Active | P1 |
| **Ashby** | 3 | 3 | 4 (read API; assisted apply) | 4 | ✅ Active | P1 |
| **Lever** | 2 | 3 | 4 (read API; assisted apply) | 4 | ✅ Active | P2 |
| **Internshala** | 5 | 5 | 2 (no API; needs partner feed) | 2 (feed upkeep) | ⏳ Seam (needs feed) | **P1 (business-blocked)** |
| **Wellfound** | 2 | 2 | 2 (no API; needs feed) | 2 | ⏳ Seam (needs feed) | P3 |
| Adzuna / Jooble | 3 | 2 | 4 (keyed API) | 3 | ⏳ Keyless | P2 (cheap India breadth) |
| Naukri / Foundit | 5 | 4 | 1 (Akamai bot-blocked, no API) | 1 | ❌ Not viable | P4 (partnership-only) |

### Recommended sequencing
1. **P0 — JSearch hardening** (this is the India engine): add the 200/mo **quota
   counter + admin alert**, and tune the default India query for internships/fresher +
   priority domains. *(small, code-only)*
2. **P0 — India-first ranking** (§2 Option A): guarantee India-above-US ordering.
   *(small, code-only — highest ROI for the reported symptom)*
3. **P2 — Adzuna + Jooble** (keyless): free-ish keyed APIs with decent India breadth;
   cheap incremental coverage. Just need keys (like JSearch).
4. **P1 — Internshala feed** (business track): pursue affiliate/partner feed → flips the
   ready seam on; biggest India-internship win once unblocked.
5. **P3 — Wellfound feed**: only if a licensed feed becomes available; low India ROI.
6. **P4 — Naukri/Foundit**: partnership-only; do not attempt scraping (Akamai-blocked +
   ToS). Revisit only with an official agreement.

### Guiding principles (unchanged)
- **Lawful sources only** — official APIs / licensed feeds; never scrape robots-disallowed
  sites or fabricate listings.
- **India + internship coverage first**; automation feasibility and maintenance cost break
  ties.
- **Keyed/feed providers stay dormant seams** (`available()==False`) until configured — no
  dead code, no false "Source Pending" surprises.

---

## Summary of code-only work (if/when approved — none done here)
| Item | File(s) | Effort |
|---|---|---|
| India-first tiered sort (§2A) | `app/routers/jobs.py`, `tests/test_india.py` | ~30 min |
| JSearch quota counter + admin signal (§1/§5) | `app/jobs/providers/jsearch.py`, admin Ops | ~1–2 h |
| Wellfound feed activation (§3) | config + `tests/test_wellfound.py` | ~1–2 h *(needs feed)* |
| Adzuna/Jooble enablement (§5) | `.env` keys only | minutes *(needs keys)* |

_No providers were modified, added, or enabled in producing this plan._
