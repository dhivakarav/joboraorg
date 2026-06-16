# India-First Provider Expansion — Roadmap

_Research & design only. No code, no implementation. Date: 2026-06-12._
_**LinkedIn removed from the roadmap** (partner-only, no open jobs API)._

## Executive summary
The four India leaders — **Internshala, Naukri, Indeed India, Foundit** — are the
highest-value sources for Indian internships/fresher jobs, but **none offers a free
public candidate-listings API**, and **all are gated behind business agreements**:
- **No official public discovery API** for any of them.
- **Naukri & Foundit are Akamai bot-protected** — even `robots.txt` returns
  "Access Denied" to non-browser clients (verified) → programmatic/scraped access is
  technically blocked **and** disallowed.
- **Internshala** `robots.txt` disallows all job/search/detail/API paths and blocks
  AI/LLM bots site-wide (per `INTERNSHALA_FEASIBILITY_REPORT.md`).
- **Indeed**'s old Publisher (search) API is **closed to new publishers**; current
  Indeed APIs (Job Sync, Indeed Apply) are **employer/ATS-partner** facing.

**Consequence:** every one of the four requires a **licensed/partner data feed**
(a commercial agreement), none supports **assisted apply** (all account-gated +
bot-blocked + ToS), and none exposes **application IDs / confirmation evidence**
(so **no Verification**). Jobora's existing **JSearch (Google for Jobs)** provider
already surfaces many of these listings **legally via Google** — the pragmatic
interim path to India coverage **without** signing four deals.

## Capability matrix (what each can support)
| Provider | Discovery | Tracking | Assisted Apply | Verification |
|---|---|---|---|---|
| Internshala | ⚠️ licensed feed only | ✅ (once discovered) | ❌ account-gated | ❌ no app id |
| Naukri | ⚠️ partnership only | ✅ | ❌ bot-blocked + account-gated | ❌ |
| Indeed India | ⚠️ partner program only | ✅ | ❌ "Indeed Apply" is employer/ATS-only | ❌ |
| Foundit | ⚠️ partner API only | ✅ | ❌ account-gated | ❌ |
| _(JSearch — already built)_ | ✅ live (licensed aggregator) | ✅ | ❌ (Track & Apply) | ❌ |

> **Tracking** = Jobora records the role + deep-links the user to apply on the
> source (no automation). **Assisted Apply / Verification** are infeasible for all
> four (account-gated apply, anti-bot, no exposed confirmation id).

---

## Per-provider detail

### 1. Internshala — highest value, no API
| Field | Finding |
|---|---|
| **API available?** | ❌ No (no official jobs API) |
| **Partner access required?** | ✅ Yes — a **licensed data feed / data-share agreement** is the only legal path |
| **Internship coverage** | ⭐⭐⭐⭐⭐ India's #1 internship platform — the single best internship source |
| **Fresher coverage** | ⭐⭐⭐⭐ strong (fresher jobs + "jobs" vertical) |
| **India coverage** | ⭐⭐⭐⭐⭐ India-native |
| **Automation feasibility** | Discovery only via feed; **no** assisted-apply (account-gated, AI-bot-blocked, robots disallows) |
| **Effort** | **~1–2 days once a feed is licensed** (the gated seam already exists: `INTERNSHALA_FEED_URL`); **blocked** without a deal |
| Legal path | Partnership/data license with Internshala (`employer@internshala.com`/partnerships). No scraping. |

### 2. Naukri (Info Edge) — large fresher pool, no API, bot-blocked
| Field | Finding |
|---|---|
| **API available?** | ❌ No public candidate-listings API ("product as a solution, not a service") |
| **Partner access required?** | ✅ Yes — **direct data-license/partnership with Info Edge** is the only legal path |
| **Internship coverage** | ⭐⭐⭐ moderate (internship vertical exists; fresher/experienced-heavy) |
| **Fresher coverage** | ⭐⭐⭐⭐⭐ India's largest fresher/jobs board |
| **India coverage** | ⭐⭐⭐⭐⭐ India-dominant |
| **Automation feasibility** | **Blocked** — Akamai bot protection denies non-browser access (robots.txt itself 403s); scraping disallowed & technically blocked; apply is account-gated |
| **Effort** | **Blocked on business**; technically low once a licensed feed exists |
| Legal path | Commercial data agreement with Info Edge. Third-party scrapers (TheirStack/Apify/ScrapingBee) are **not** legal/official — excluded. |

### 3. Indeed India — huge reach, publisher API closed
| Field | Finding |
|---|---|
| **API available?** | ⚠️ Partial — old **Publisher (search) API closed to new publishers**; current APIs (**Job Sync**, **Indeed Apply**) are **employer/ATS-partner** facing, not candidate-search |
| **Partner access required?** | ✅ Yes — an **Indeed partner agreement** (and Indeed Apply targets employers/ATS) |
| **Internship coverage** | ⭐⭐⭐ moderate–high |
| **Fresher coverage** | ⭐⭐⭐⭐⭐ very high |
| **India coverage** | ⭐⭐⭐⭐⭐ very high |
| **Automation feasibility** | Discovery only via partner feed; robots disallows `/api/getrecjobs`, `/applystart`, `/advanced_search`; **Indeed Apply ≠ third-party autofill** → no assisted apply |
| **Effort** | **Medium**, gated on partner approval |
| Legal path | Indeed Partner program (`docs.indeed.com`). Note: **JSearch already surfaces many Indeed-origin listings via Google for Jobs, legally** — the practical interim route. |

### 4. Foundit (Monster India) — the most tractable *official* path
| Field | Finding |
|---|---|
| **API available?** | ⚠️ Yes, **via partner/developer program** (Monster offers job-search/posting/resume APIs; key + agreement required) — **not** openly public |
| **Partner access required?** | ✅ Yes — **partner/developer agreement with foundit/Monster** + API key |
| **Internship coverage** | ⭐⭐⭐ moderate |
| **Fresher coverage** | ⭐⭐⭐⭐ strong |
| **India coverage** | ⭐⭐⭐⭐ India + ME + SE-Asia |
| **Automation feasibility** | Discovery via partner API (if granted); consumer site is Akamai bot-blocked; apply account-gated → no assisted apply |
| **Effort** | **Medium** (partner onboarding + map the API → `RawJob`); **most feasible official API** of the four |
| Legal path | foundit/Monster partner/developer program (`hiring.monster.com` / partner team). |

---

## Recommended sequence (design intent — not implemented)
1. **Interim, build-free: lean on JSearch** (already live, gated on a key) for India
   internship/fresher coverage via Google for Jobs — it legally surfaces many
   Naukri/Indeed/Foundit-origin listings today. **Set `JSEARCH_API_KEY`** to unlock
   it. This is the fastest India-coverage win with **zero new integrations**.
2. **Pursue partnerships in value order** (business track, parallel to engineering):
   - **Internshala** (highest internship value) → licensed feed.
   - **Foundit** (most tractable *official* API) → partner/developer access.
   - **Indeed India** → partner program (note JSearch overlap).
   - **Naukri** → data license with Info Edge (largest fresher pool; hardest access).
3. **When any feed/partner key arrives, wiring is the same gated-provider pattern**
   (like Adzuna/Jooble/JSearch): `available()=False` until configured → map the
   feed → `RawJob` → the existing eligibility/internship-filter/tracking pipeline
   lights up. Effort **~1–2 days per feed**.

## Hard constraints to honor (all four)
- **No scraping** — robots-disallowed and/or Akamai-blocked; third-party scrapers
  (Apify/ScrapingBee/TheirStack) are excluded.
- **No assisted apply / no verification** — apply is account-gated and these sources
  expose no confirmation id; Jobora can only **discover + track + deep-link**.
- **Keyed/feed providers stay gated** (inert until configured) — no breakage when
  unconfigured.

## Sources
robots.txt checks: `in.indeed.com/robots.txt` (open-ish; `/api/getrecjobs`,
`/applystart` disallowed); `naukri.com` + `foundit.in` → **Akamai "Access Denied"**
(bot-blocked). Endpoint probes: `naukri.com/jobapi` 403, `foundit.in/api` 403,
`developer.indeed.com` 301. Plus prior `INTERNSHALA_FEASIBILITY_REPORT.md`.
- [Naukri API status (Quora) — no public API](https://www.quora.com/Is-there-any-API-integration-for-Naukri-com) ·
  [Info Edge recruitment products](https://www.infoedge.in/Businesses/Recruitment)
- [Indeed Partner docs — Job Sync API](https://docs.indeed.com/job-sync-api/job-sync-api-guide) ·
  [Indeed API terms](https://docs.indeed.com/legal-terms/additional-api-terms-and-guidelines)
- [Partner with Monster/foundit](https://hiring.monster.com/solutions/talent-management/partner-with-monster/)
- Internshala: see `INTERNSHALA_FEASIBILITY_REPORT.md` (no API; robots disallows; AI-bots blocked).
