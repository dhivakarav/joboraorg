# Jobora — Final Project Status

_Date: 2026-06-12. Snapshot of the completed build. No further development is
planned after this report (development is stopped per request)._

Jobora is an honest, student-focused job-application platform: it discovers **real**
jobs from real providers, ranks them for early-career users, and tracks
applications with **evidence-gated** statuses — it never claims a submission that
didn't happen.

---

## ✅ Completed features

### Discovery & matching
- **Real job aggregation** across 11 registered providers (5 active no-key + 6
  gated) — no scraping, no fabricated listings.
- **Eligibility scoring** (Excellent / Good / Possible / Not Recommended) tuned for
  students/freshers; hides senior · staff · principal · lead · manager · director ·
  architect · 3+ yrs · PhD-only · Master's-required.
- **Internships & New-Grad hard filter** (default ON for students/freshers): shows
  only intern/new-grad/graduate-program/fresher/entry-level/associate signals.
- **"Why matched?"** reasons + INR salary/stipend normalization + dedupe +
  provider-level + aggregate caching (cold search ~5.6s → repeat ~3ms).

### Application flows (integrity-gated)
- **Greenhouse → Track & Apply on Company Site**: opens the official page, records
  a **Tracked** event. No "Auto-Apply" wording anywhere.
- **Lever & Ashby → Assisted Apply wizard**: prefill from the user's real profile →
  review → user completes captcha & submits → **record evidence** (confirmation URL
  + reference id + screenshot).
- **Canonical statuses**: Draft · Tracked · Manual Apply · Submitted · **Verified
  Submitted** (requires id + confirmation URL + screenshot) · Failed. The retired
  "Applied" label cannot surface anywhere.
- **Verification Center**: the single source of submission proof.

### Accounts, UX, ops
- Auth (signup → admin approval → login), JWT access+refresh+revocation, bcrypt,
  email verification, password reset.
- Responsive UI (desktop + mobile drawer), skeleton loaders, empty/error/success
  states, first-time "How Jobora works" walkthrough, tooltips.
- Resume upload + parsing (name/email/location/skills/education reliable; phone
  extraction hardened) with PII encryption at rest + graceful-degrade on decrypt
  failure.
- **Beta systems**: invite codes (gated registration), in-app feedback/bug widget,
  and an **Admin → Operations** screen (metrics funnel, feedback triage, invite
  management).
- Monitoring wired (gated): Sentry + PostHog (signup, login, resume, search,
  job_click, tracked, manual_apply, verified_submitted).
- Rate limiting (Redis-backed), global error handling, health/ready probes.

### Integrity invariants (held throughout)
No fake jobs · no mock applications in production · no fabricated evidence · no
hardcoded "Applied" · real providers + real data only.

---

## ✅ Completed tests
- **Backend unit/integration: 44 passing** (`pytest`) — security/B2, status
  transitions, eligibility, search caching, Greenhouse Track & Apply, Lever/Ashby
  assisted apply + evidence gate, admin operations, JSearch provider, internshala
  gating.
- **End-to-end (Playwright): 13/13 passing** — signup, login, resume upload+parse,
  Find Jobs, internship filter, dashboard, activity log, verification center, admin
  operations, Greenhouse Track & Apply, Lever/Ashby assisted, logout, mobile drawer.
  Captures **0 console errors · 0 failed API requests · 0 uncaught exceptions** and
  produced 13 page screenshots. (This suite caught and closed a real runtime bug.)
- ATS submit pipelines validated G0–G3 against controlled mocks (Greenhouse
  enabled; Lever/Ashby assisted, captcha-gated).

---

## ⏳ Remaining optional tasks (non-blocking; not being worked on)
- Browser/E2E tests for additional UI interactions (current E2E covers all major
  flows; deeper component tests are optional).
- Resume parsing: intern/months → 0 years (correct for the audience) and rare prose
  education-line noise — minor, user-correctable via the edit form.
- Real-device mobile pass (layout is responsive; Playwright covers the mobile
  drawer at 390px, but physical-device QA is recommended).
- Internshala: **blocked on a licensed/partner data feed** (no official API; robots
  disallows). Gated seam ready; a feed wiring is ~1–2 days *if* a partnership is
  signed. Treated as a business track, not a build task.
- Additional providers from `PROVIDER_EXPANSION_REPORT.md` (SmartRecruiters, The
  Muse, Careerjet, Jobicy) — researched & ranked, **not** being implemented per
  the current directive.

---

## 🚀 Deployment requirements (not performed; documented only)
The product is **deploy-ready in code**; standing up infrastructure is the only
remaining gate (see `DEPLOYMENT_GUIDE.md` / `DEPLOY_CHECKLIST.md` / `RAILWAY_SETUP.md`).
Required before inviting real users:
1. Managed **PostgreSQL** (`DATABASE_URL`) — dev uses SQLite.
2. Managed **Redis** (`REDIS_URL`) — shared rate-limit/cache/queue.
3. **S3 / R2** object storage (resumes + evidence) — dev uses local disk.
4. Stable, vaulted **`JWT_SECRET`** + **`CREDENTIAL_KEY`** (prod refuses to start
   without them).
5. **SMTP** (verification/approval email) and **`SENTRY_DSN`** + **`POSTHOG_API_KEY`**.
6. `BETA_INVITE_REQUIRED=1`, `EXPOSE_RESET_TOKEN=0`, `CORS_ORIGINS`, `APP_BASE_URL`.
7. Run the RQ **worker** as a separate process at scale; migrations auto-apply on
   boot (head `c3d4e5f6a7b8` + `d4e5f6a7b8c9`).

Estimated capacity (from the readiness report): 10 users comfortable · 100 OK
(separate worker, tune limits) · 1000 needs Postgres scaling + API replicas + a
load test.

---

## 🔌 Provider status (11 registered)
| Provider | Type | Status | Notes |
|---|---|---|---|
| Remotive | Public API | ✅ Active | Remote jobs |
| Arbeitnow | Public API | ✅ Active | Remote/EU |
| Greenhouse | Official board API | ✅ Active | Track & Apply; submit pipeline verified |
| Lever | Official postings API | ✅ Active | Assisted Apply (hCaptcha) |
| Ashby | Official posting API | ✅ Active | Assisted Apply (reCAPTCHA, SPA) |
| Adzuna | Keyed API | 🔑 Gated | needs `ADZUNA_APP_ID/KEY` (India/SG) |
| Jooble | Keyed API | 🔑 Gated | needs `JOOBLE_API_KEY` |
| **JSearch** | Keyed API (Google for Jobs) | 🔑 Gated | needs `JSEARCH_API_KEY` (India + remote + internships) — newest addition |
| Workable | Account token | 🔑 Gated | needs authorized account token |
| Internshala | Licensed feed | ⛔ Gated | no official API; needs a licensed feed (partnership) |
| Wellfound | Licensed feed | ⛔ Gated | no public API; robots-disallowed |

Gated providers are inert (`available()=False`) until configured — they never break
discovery and never scrape.

---

## Verdict
**Feature-complete and integrity-sound for a closed beta.** Backend 44/44 and
Playwright 13/13 green; zero console/network/exception errors across all flows.
The only gate to a live 20-user beta is **infrastructure provisioning** (a config
task, documented in the deploy guides). Internshala and further providers remain
research-complete but intentionally unbuilt.

**Development is now stopped, as requested.**

### Reference documents
Audits/reports: `PRODUCT_COMPLETION_REPORT.md`, `FINAL_PROJECT_AUDIT.md`,
`PLAYWRIGHT_REPORT.md`, `BETA_READINESS.md`, `INFRASTRUCTURE_AUDIT.md`,
`UX_AUDIT.md`, `ELIGIBILITY_FILTER_REPORT.md`, `INTERNSHIP_FILTER_REPORT.md`,
`GREENHOUSE_FLOW_REPORT.md`, `ASSISTED_APPLY_UI_REPORT.md`,
`VERIFICATION_CENTER_REPORT.md`, `SEARCH_PERFORMANCE_REPORT.md`,
`ADMIN_UI_REPORT.md`, `TEST_COVERAGE_REPORT.md`, `RESUME_PARSER_REPORT.md`,
`MOBILE_AUDIT_REPORT.md`, `PROVIDER_EXPANSION_REPORT.md`,
`INTERNSHALA_FEASIBILITY_REPORT.md`, `JSEARCH_INTEGRATION_REPORT.md`.
Setup/deploy: `DEPLOYMENT_GUIDE.md`, `DEPLOY_CHECKLIST.md`, `RAILWAY_SETUP.md`,
`ENV_VARIABLES.md`, `ROLLBACK_PLAN.md`, `JSEARCH_SETUP.md`, `BETA_TEST_PLAN.md`.
