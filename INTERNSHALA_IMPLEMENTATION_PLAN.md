# Internshala — Implementation Plan

_Plan only; nothing implemented here. Sequenced so the **compliant, code-only**
work ships now and the **data integration** is unblocked by a business agreement.
Companions: `INTERNSHALA_FEASIBILITY_REPORT.md`, `INTERNSHALA_PROVIDER_DESIGN.md`._

## Guiding decision
Internshala is **not** an engineering integration today (no lawful data path). So the
plan is: **(A)** harden compliance + ship the compliant hand-off now; **(B)** pursue
the licensed feed as a business track; **(C)** wire the feed in fast once signed.
Throughout: **no scraping, no assisted/auto apply, no anti-bot evasion.**

---

## Phase 0 — Compliance hardening (code-only, do now) · ~0.5 day
**Goal:** make it impossible to silently scrape Internshala, fixing the verified
gate defect.
1. **Fix `app/jobs/robots.py`** — `can_fetch()` fails open on Internshala's
   wildcard-heavy robots.txt (returns allow for disallowed paths). Options:
   - Replace `urllib.robotparser` with a parser that honors `Disallow` wildcards
     (e.g. a vetted lib or a small correct matcher), **or**
   - Make `can_fetch` **fail closed** when the parse is ambiguous/empty.
   - Add unit tests using Internshala's actual robots.txt asserting
     `can_fetch('/internship/search/') == False`, `'/api/' == False`.
2. **Provider guard (defense-in-depth):** in the Internshala provider, **refuse**
   any `FEED_URL` whose host is `internshala.com` unless `INTERNSHALA_FEED_TRUSTED=1`
   *and* the path is feed-shaped — so the seam can never fetch Internshala HTML.
3. Tests: extend `tests/` to prove the seam returns `[]` and never hits
   internshala.com without an explicit trusted feed.

**Deliverable:** the seam is provably non-scraping; gate correct. No user-visible change.

## Phase 1 — Compliant manual hand-off (code-only, optional now) · ~0.5–1 day
**Goal:** give users *some* Internshala value today without any data ingestion.
1. Frontend: a **"Search internships on Internshala ↗"** deep-link (Find Jobs empty-
   state / sources strip), opening the public site (user browses/applies).
2. Optional **"Track an Internshala application"**: user pastes the listing URL +
   title they applied to → recorded as **Tracked** in Activity Log (Jobora-side only;
   no status read-back, consistent with the evidence model).
3. Pre-fill limited to **copy-my-profile-to-clipboard** (never drives their form).
4. Tests: hand-off records a Tracked row; no Internshala fetch occurs.

**Deliverable:** honest hand-off; clearly labeled "apply on Internshala". Low product
value (no in-app matching) but zero compliance risk.

## Phase 2 — Business track: secure a licensed feed (no code) · timeline unknown
**Goal:** obtain the only lawful discovery path.
1. Outreach to Internshala partnerships/employer team (e.g. `employer@internshala.com`
   / their BD) requesting a **licensed listings data feed** or data-sharing agreement.
2. Define written scope: fields, refresh cadence, attribution, allowed use, rate
   limits, takedown terms.
3. Confirm the feed is delivered from a **non-internshala host** (or an explicitly
   licensed endpoint) so it is unambiguously authorized.
4. **Gate:** Phase 3 starts **only** when a signed agreement + feed spec exist.

**Deliverable:** a contract + feed endpoint, or a documented "no" (then Internshala
stays JSearch-only).

## Phase 3 — Wire the licensed feed (code-only, after Phase 2) · ~1–2 days
**Goal:** activate discovery via the seam.
1. Implement `InternshalaProvider.fetch()` mapping (per Provider Design §2) →
   `RawJob` (title, company, India-tagged location, remote, stipend→INR, duration,
   `employment_type="internship"`, apply_url, `external_id`).
2. Configure `INTERNSHALA_FEED_URL` (+ `INTERNSHALA_FEED_TRUSTED=1` for the licensed
   host). Provider flips `available()=True` automatically.
3. **Dedupe vs JSearch** (Provider Design §3): canonical-URL/near-match; prefer the
   Internshala-native record.
4. Verify tiering: all records → `india_tier` Tier 1/2 (India-first ranking) and the
   Internship/Fresher tabs (no ranking code changes needed).
5. Tests (`tests/test_internshala.py`, mocked feed — no network): gating, mapping,
   India-tagging→Tier 1/2, stipend→INR, internship inference, dedupe-vs-JSearch.
6. Run backend suite + `npm run build`. Produce an activation/coverage report
   (live counts vs JSearch — the comparison the feasibility report could only
   estimate).

**Deliverable:** Internshala discovery live, India-/internship-first, deduped — a
genuine Tier-1 provider.

---

## Effort & dependency summary
| Phase | Work | Effort | Blocker | Ship now? |
|---|---|---|---|---|
| 0 — compliance hardening | code | ~0.5 d | none | ✅ yes |
| 1 — manual hand-off | code | ~0.5–1 d | none | ✅ optional now |
| 2 — licensed feed | business | unknown | partnership | ⛔ external |
| 3 — wire feed | code | ~1–2 d | Phase 2 signed | after Phase 2 |

## Explicit non-goals (forbidden — will not implement)
- Scraping search/detail/API or harvesting sitemap URLs.
- Assisted apply or automated apply on Internshala.
- Driving an authenticated Internshala session or pre-filling their form.
- Reading application status from Internshala.
- Any captcha solving / anti-bot evasion.

## Recommendation
Do **Phase 0 now** (it closes a real compliance defect regardless of Internshala).
Treat **Phase 1** as optional polish. Run **Phase 2** as a parallel business effort.
Keep **JSearch as the India-internship engine** in the meantime — it already
delivers the majority of the addressable India-internship coverage (see Feasibility
§5). Only invest in Phase 3 once a licensed feed is signed; the marginal coverage
gain over JSearch is incremental, so prioritize accordingly.
