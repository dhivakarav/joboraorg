# Beta Test Plan

Goal: validate Jobora with a small **invited** cohort, find the top failure
points, and decide go/no-go for a wider beta. Target: **10 → 20 real users.**

## Pre-flight checklist (operator)
- [ ] Deployed per `DEPLOYMENT_GUIDE.md` (Postgres + Redis + S3/R2 + stable secrets).
- [ ] `BETA_INVITE_REQUIRED=1`; generate codes via `POST /api/admin/invites`.
- [ ] `SENTRY_DSN` + `POSTHOG_API_KEY` set; verify events arrive.
- [ ] `/api/ready` shows DB ok + cache `redis`.
- [ ] Admin account works; approval flow tested.
- [ ] Feedback widget reachable on every page; submissions show in `/api/admin/feedback`.

## Cohort
- **Wave 1 — 10 users** (close contacts, AI/ML students/freshers). Hand-hold,
  watch sessions where possible.
- **Wave 2 — +10 users** after Wave-1 blockers fixed.

## Core scenarios each tester runs
1. **Onboarding:** register with invite code → admin approves → login → pick
   seeker type.
2. **Resume:** upload a real resume → confirm parsed fields look right.
3. **Discovery:** Find Jobs returns results; internships-&-new-grad filter is ON;
   "Why matched?" makes sense; toggle off to see all eligible.
4. **Track:** click a job → it appears in Activity Log as **Tracked**.
5. **Assisted Apply (Lever/Ashby):** prepare → open real apply URL → (optionally)
   complete + record evidence → status reflects reality (never "Applied" w/o proof).
6. **Feedback:** submit one feedback + one bug via the widget.

## Metrics to watch (PostHog funnel)
`signup → login → resume_uploaded → job_search → job_click → tracked_job →
manual_apply → verified_submitted`. Drop-off at any step = a failure point.

## Top failure points to watch (hypotheses)
| Risk | Signal | Mitigation |
|---|---|---|
| Resume parse misses fields | feedback + low search relevance | manual edit screen; log parse failures |
| Sparse internship results | few cards with filter ON | "show all eligible" toggle is visible; widen later (post-beta) |
| Assisted-apply confusion | bug reports on apply step | the assisted wizard UI (currently endpoints only) |
| Undecryptable resume | 500s | **fixed** — degrades to re-upload prompt |
| Email not delivered | users stuck pre-approval | set real SMTP; monitor |
| Rate limits too tight | 429s | tune `RL_*` for beta |

## Exit criteria for wider beta
- ≥ 80% of Wave-1 complete scenarios 1–4 without help.
- 0 open **high**-severity bugs.
- No integrity regressions (no "Applied" without evidence; no fabricated data).
- Funnel shows users reaching `tracked_job`.

## Bug + feedback flow
- In-app **💬 Feedback** widget → `feedback` table → admin `/api/admin/feedback`.
- High-severity bugs triaged daily; fixes shipped before Wave 2.
