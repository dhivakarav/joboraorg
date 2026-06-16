# Beta Readiness Report

_Date 2026-06-11. Evidence-based; no Greenhouse/Lever/Ashby/matching/integrity
logic was changed in this milestone._

## ✅ Complete
- **Real discovery only** (no fake jobs/boards); strict eligibility + internships-&-
  new-grad filter; "Why matched?" on every card.
- **Integrity model:** canonical statuses; "Applied" retired; Verified Submitted
  requires confirmation + id + screenshot. Verified live: **0 "Applied" leaks**.
- **ATS:** Greenhouse pipeline G0–G3 verified; Lever + Ashby **Assisted Apply**
  backend (prefill → review → record evidence), `manual_only` enforced.
- **Monitoring code:** Sentry init (gated) + **PostHog analytics module** with 8
  events wired — `signup, login, resume_uploaded, job_search, job_click,
  tracked_job, manual_apply, verified_submitted` (+ application_started/submitted).
  Gated: no-ops until keys set.
- **Closed-beta systems:** single-use **invite codes** (admin-generated, optional
  registration gate), **feedback + bug widget** on every page, **admin metrics**
  (funnel + applications + feedback + invites).
- **Infra config:** Dockerfile, `entrypoint.sh` (honors `$PORT`, runs migrations),
  `railway.json`, `render.yaml`, env checklist, `DEPLOYMENT_GUIDE.md`.
- **Resilience fix:** undecryptable resume no longer 500s the app.
- **21/21 backend tests pass; frontend builds clean.**

## ⏳ Partial
- **Monitoring is dormant** until `SENTRY_DSN` + `POSTHOG_API_KEY` are set (code ready).
- **Assisted-apply front-end wizard** not built — users reach Lever/Ashby via the
  real apply URL hand-off (functional but rough).
- **Real-user testing not yet run** — 0 beta users to date; plan + tooling ready.
- **Worker** runs in-process by default (fine for ≤100 users; separate it for scale).

## ⛔ Blocking a safe 20-user beta (all are provisioning, not code)
1. **Production infra not stood up** — currently SQLite + **ephemeral secrets**
   locally. MUST deploy on **Postgres + Redis + S3/R2 + stable JWT/CREDENTIAL keys**.
2. **No real email** — `SMTP_*` unset → verification/approval emails go to console,
   so invited users can't complete sign-in. Configure SMTP.
3. **Monitoring keys unset** — set Sentry + PostHog so beta is observable.

## Readiness
- **Feature/code readiness: ~85%.**
- **Deploy-ready-today (as currently running): ~40%** (infra + email + keys missing).
- **After the `DEPLOYMENT_GUIDE.md` checklist: ~90%** for a 20-user closed beta.

## Estimated capacity
| Scale | Verdict | Needs |
|---|---|---|
| **10 users** | ✅ Comfortable | 1 small API instance, starter Postgres + Redis, S3, SMTP |
| **100 users** | ✅ OK | Separate worker process; tune `RL_*`; provider cache headroom; monitor |
| **1000 users** | ⚠️ Needs work | Postgres scaling + read replica, 2–3 API replicas (Redis-shared limits already supported), dedicated worker pool, provider rate-limit budgeting, **load test first** |

---

## Can 20 real beta users safely use Jobora today?

### NO — not as it stands this minute; **YES after a ~1-day provisioning checklist.**

**Why not right now (evidence):** the app is running on **local SQLite with an
ephemeral `CREDENTIAL_KEY`** (encrypted resumes don't survive restarts — observed),
**no SMTP** (invited users wouldn't receive approval/verification email), and
**no Sentry/PostHog keys** (the beta would be unobservable). These are deployment/
config gaps, not code gaps.

**Why "safely" is otherwise satisfied (evidence):** fail-closed secrets, JWT
refresh+revocation, rate limiting, **PII encryption** (with graceful degradation),
**integrity intact** (0 "Applied" leaks; Verified Submitted requires real proof;
no fake jobs/fabricated evidence), real discovery (2,267 Greenhouse jobs), and
21/21 tests passing.

**To get to YES (from `DEPLOYMENT_GUIDE.md`):** deploy on Railway with
**Postgres + Redis + S3/R2**, set **stable `JWT_SECRET`/`CREDENTIAL_KEY`**,
configure **SMTP**, set **`SENTRY_DSN` + `POSTHOG_API_KEY`**, enable
**`BETA_INVITE_REQUIRED=1`** and generate codes. Then run **Wave 1 (10 users)** per
`BETA_TEST_PLAN.md`, fix high-severity bugs, and open **Wave 2 (20 users)**.

**Bottom line:** Jobora is **feature- and integrity-ready** for a 20-user closed
beta; it is **not yet deployed**. Complete the provisioning checklist (≈1 day) and
the answer becomes **YES**.
