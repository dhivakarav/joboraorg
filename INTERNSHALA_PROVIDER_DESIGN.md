# Internshala Provider — Design

_Design only; no implementation. Assumes the **only compliant data path**: an
**authorized/licensed feed** (`INTERNSHALA_FEED_URL`). No scraping, no apply
automation. Companion to `INTERNSHALA_FEASIBILITY_REPORT.md`._

## 0. Design constraints (from feasibility)
- **Data in only via a licensed feed.** No scraping; the gated seam must refuse to
  fetch Internshala HTML.
- **Apply is a hand-off**, never automated/assisted (login-gated + ToS + anti-bot).
- Must reuse Jobora's existing pipeline (RawJob → eligibility → matching → tiered
  India-first ranking → tracking) so Internshala "lights up" without new plumbing.

## 1. Provider interface
Implements the standard `Provider` contract (`app/jobs/base.py`), like JSearch/Adzuna:

```
class InternshalaProvider(Provider):
    name = "Internshala"
    requires_key = True          # gated; inactive without a feed
    official_api = False         # licensed feed, not a public API

    def available(self) -> bool:                 # True only when INTERNSHALA_FEED_URL set
    async def fetch(self, client, query, location, limit) -> list[RawJob]:
    def unavailable_reason(self) -> str:         # explains the partnership gate
```

- **Already scaffolded** in `app/jobs/providers/internshala.py` (gated seam +
  `INTERNSHALA_FEED_URL` / `INTERNSHALA_FEED_TRUSTED`). Design = fill `fetch()`
  mapping + harden the gate.
- **Adapter** `app/adapters/internshala.py`: `manual_only=True`,
  `supports_auto_submit=False` → discovery surfaces listings; apply is Track & Apply
  (deep-link). Never assisted/auto.

## 2. Search implementation (licensed-feed path)
```
fetch(query, location, limit):
  if not FEED_URL: return []                      # gate 1: no feed → nothing
  if not _feed_allowed(FEED_URL): return []       # gate 2: robots/allowlist (see §8)
  data = GET FEED_URL ?q=query&location=location&limit=…   # feed's own params
  return [ _map(rec) for rec in data ][:limit]
```
- **Query/location** passed to the feed if it supports server-side filtering; else
  fetch a page and filter client-side via the existing `matches_filters`.
- **India-first by default:** request `location=India` (or pass through the user's
  India city) — Internshala is India-only, so all records are India anyway.
- **Failure isolation:** any error → `[]` (a provider never breaks aggregate search).

### Field mapping: feed record → `RawJob`
| RawJob field | Feed source | Notes |
|---|---|---|
| `source` | `"Internshala"` | constant |
| `title` | `profile`/`title` | |
| `company` | `company_name` | |
| `location` | `location` | tag `", India"` when blank (India-only platform) → Tier 1/2 |
| `remote` | `work_from_home`/`is_remote` | "Work from home" internships → remote |
| `salary` / stipend | `stipend` | → INR via existing currency module |
| `employment_type` | `"internship"` (or `infer_employment_type(title)`) | feeds Internship/Fresher tabs |
| `duration` | `duration` | e.g. "3 Months" → internship-duration filter |
| `apply_url` | `url` | the public listing the user is **deep-linked** to |
| `external_id` | `f"internshala-{id}"` | dedupe key |
| `posted_at` | `start_date`/`posted` | |

## 3. Deduplication
- Reuse the aggregator's **fingerprint** dedupe (`RawJob.fingerprint` from
  title+company+location/url).
- **Cross-provider overlap (important):** JSearch already surfaces many Internshala
  listings (Google-indexed). To avoid double-showing the same internship:
  - Prefer a **canonical-URL match** (normalize `internshala.com/…/detail/<id>`),
    plus a (company, title, location) near-match fallback.
  - **Precedence:** keep the **Internshala-native** record (richer stipend/duration)
    over the JSearch echo when both exist.

## 4. Resume matching
- **No change** — Internshala `RawJob`s flow through the existing `score_job` /
  matching engine (skills/keywords/title overlap with the user's parsed resume).
- Stipend in INR + `duration` improve match/eligibility signals for students.

## 5. Eligibility filtering
- Reuse `eligibility()` + `early_signal()`. Internshala is intern/fresher-dense, so
  most records carry an early-career signal; the existing senior/PhD/3-yr filters
  still apply (rarely triggered here).

## 6. Internship-first ranking
- `employment_type="internship"` + title inference → counts under the Internship/
  Fresher tabs and `internships_only` hard filter (already in place). No new code.

## 7. India-first ranking (reuse the tier system)
- All Internshala records are India → `india_tier` returns **Tier 1** (on-site) or
  **Tier 2** (work-from-home/remote-India). They therefore **rank above US/EU**
  automatically under the existing `(india_tier, -_rank_key)` sort. Mapping must
  ensure the location is India-tagged (see §2 mapping) so Tier 1/2 is assigned —
  same pattern as the Adzuna `", India"` fix.

## 8. Compliance gate hardening (required before any feed)
- The current `can_fetch()` **fails open** on Internshala (verified). Design:
  1. For a **non-internshala licensed host**, gate on `INTERNSHALA_FEED_TRUSTED=1`
     (operator asserts the feed is licensed) — do **not** rely on robots there.
  2. **Never** fetch `internshala.com` HTML from the provider — the feed must be the
     licensed endpoint only. Add an explicit guard: if `FEED_URL` host is
     `internshala.com`, **refuse** unless `*_TRUSTED` is set *and* the path is feed-
     shaped (defense-in-depth).
  3. Fix `app/jobs/robots.py` so the gate is correct generally (see Implementation
     Plan) — but Internshala safety must **not depend** on it.

## 9. Manual hand-off (fallback when no feed — compliant today)
If/while no feed exists, the only compliant Internshala presence:
- A **"Search internships on Internshala ↗"** deep-link (to the public site) — the
  **user** browses/applies; Jobora ingests **no** listing data.
- Optional: a **"Track an Internshala application"** entry where the user pastes the
  listing URL/title they applied to → Jobora records it as **Tracked** (Jobora-side
  tracking only; no status read-back).
- **Pre-fill:** limited to **copying the user's own Jobora profile/resume fields to
  clipboard** for them to paste — Jobora must **not** drive Internshala's form.

## 10. Out of scope (forbidden)
Scraping search/detail/API; harvesting sitemap URLs; assisted apply; automated
apply; reading application status from Internshala; captcha/anti-bot handling.
