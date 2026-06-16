# Internshala — Coverage Report

_Measured 2026-06-16. Grounded in real measurements + mock-feed verification. No
scraping. Native-feed live discovery requires a licensed `INTERNSHALA_FEED_URL`
(not configured), so native counts are 0 today; the via-JSearch numbers below are
real and live._

## Headline
- **Native Internshala feed:** **not configured → 0 jobs discovered** (the provider
  is gated and refuses to scrape; it activates only with a licensed feed).
- **Internshala listings reaching Jobora *today* (via JSearch/Google for Jobs):**
  **low — ~1 in 10** internship results carried an `internshala.com` apply URL in a
  live sample (see below). JSearch mostly links to LinkedIn/aggregator copies, not
  Internshala directly.
- **Capability is fully built and verified** (mock feed): the moment a licensed feed
  is wired, Internshala internships surface, tier India-first, dedupe vs JSearch, and
  feed the analytics.

## Measurement 1 — live, via JSearch (real)
Query `internship` · location `India` · JSearch (Google for Jobs):
```
JSearch returned : 10 internship/India listings
Internshala-hosted: 1
apply-url hosts  : in.linkedin.com ×5, internshala.com ×1, apna.co ×1,
                   unstop.com ×1, jobs.johnsoncontrols.com ×1, careers.marsh.com ×1
```
> Sample = 10 (JSearch free tier returns ~1 page). Indicative, not exhaustive.
> **Takeaway:** Internshala-*attributable* coverage via JSearch is **small** — Google
> usually surfaces the LinkedIn/aggregator copy of an internship, so few results carry
> an `internshala.com` apply URL. A **native Internshala feed adds the most distinct
> value** (the listings JSearch doesn't attribute to Internshala).

## Measurement 2 — capability (mock licensed feed, verified)
A representative feed (3 records) flowed through the full pipeline:
```
discovered: 3
  T1 | Bengaluru     | AI/ML Intern                  | ₹20,000 /month
  T2 | Remote, India | Full Stack Development Intern  | ₹15,000 /month
  T1 | Pune          | Software Engineer Fresher      | ₹3,00,000 /year
analytics: { internshala_total:3, internships:2, fresher:1, ai_ml:1, software:2 }
```
All India-tagged → **Tier 1/2 (ranked above global)**; stipend→INR, duration, skills
captured; analytics correct. So coverage scales 1:1 with whatever a licensed feed
delivers.

## Source analytics (goal 7) — now emitted on every search
`JobSearchOut.internshala_coverage` + the `JOB_SEARCH` analytics event now include:
`internshala_total`, `internships`, `fresher`, `ai_ml`, `software` — counting both
native-feed records **and** Internshala-hosted listings arriving via JSearch.

## Comparison (India internship coverage)
| Source | Live today | India internship coverage | Internshala-attributable |
|---|:--:|:--:|:--:|
| **JSearch** | ✅ | **High** (broad India internships) | **Low** (~10% carry internshala.com URL) |
| **Adzuna** | needs key | Medium | Negligible |
| **Internshala native feed** | ⛔ needs licensed feed | **Very High** (its own catalogue) | 100% (by definition) |
| Greenhouse/Ashby/Lever/Workable | ✅ | Low (US-centric) | None |

## Conclusion & recommendation
- **Internshala is a Tier-1 provider by data value, not yet by feasibility.** No
  lawful native data path exists without a partnership.
- **Today:** JSearch is the India-internship engine; it surfaces many internships but
  **attributes few to Internshala** — so the marginal coverage a native feed would add
  is **real and distinct**, not redundant (revises the earlier "incremental" estimate
  upward for *distinct* listings, while overall India-internship breadth via JSearch
  remains good).
- **Action:** pursue a licensed feed (business track); the code is done and gated, so
  activation + a true live coverage count is a one-config-value step once a feed exists.
- **Do not** scrape or build assisted/auto apply (forbidden + non-compliant).

_Companion docs: `INTERNSHALA_FEASIBILITY_REPORT.md`, `INTERNSHALA_PROVIDER.md`,
`INTERNSHALA_PROVIDER_DESIGN.md`, `INTERNSHALA_IMPLEMENTATION_PLAN.md`._
