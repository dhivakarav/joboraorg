# Jobora — Admin Guide

Admins approve users, monitor activity, triage feedback, and issue beta invites.
Admin pages live under `/admin/*` and require an account with `is_admin = true`.

## Becoming an admin
The admin account is **seeded from environment** at startup — set `ADMIN_EMAIL` and
`ADMIN_PASSWORD` before first boot. If unset, **no admin is created** (there are no
default credentials). A freshly-seeded admin must change its password on first
login. Email is normalized to lowercase.

## Admin pages (sidebar)
| Page | Route | Purpose |
|---|---|---|
| **Dashboard** | `/admin/dashboard` | Platform totals: users, pending approvals, approved users, total applications. |
| **User Management** | `/admin/users` | List users, view details, **approve** / **suspend**. |
| **All Applications** | `/admin/applications` | Every application across users, filter by portal / status / date. |
| **Operations** | `/admin/operations` | Beta metrics funnel, feedback/bug triage, invite-code management. |

## 1. Approving users
New signups are **pending** and cannot use the app until approved.
1. Go to **User Management**.
2. Open a user (details show resume status, application count, recent activity).
3. Click **Approve** (or **Suspend** to block access). Approved users can log in
   immediately (subject to email verification if enabled).

## 2. Operations — Metrics tab
A beta funnel + ops snapshot:
- **Users**: total / pending / approved / new this week.
- **Funnel**: signed up → uploaded resume → tracked a job.
- **Applications** by canonical status: Verified Submitted / Submitted / Manual
  Apply / Tracked-or-Draft / Failed / Total.
- **Feedback** (open / open bugs) and **Invites** (used / total).

## 3. Operations — Feedback & Bugs tab
All in-app feedback and bug reports, filterable by **All / Feedback / Bugs**. Each
row shows type, message, page, rating (feedback), severity (bug), contact email,
and date. Use this to triage during beta.

## 4. Operations — Invites tab (closed-beta gating)
When `BETA_INVITE_REQUIRED=1`, registration requires a valid **single-use** invite
code.
- **Generate codes**: choose a count (1–200) + an optional note (e.g. "Wave 1 — SRM
  students"). Codes are listed with **Available / Used** status, the redeemer's
  email, the note, and creation date. Click a code to copy it.
- Share codes with invitees; each code works once and binds to the email that
  redeems it.

## 5. All Applications
A platform-wide view of applications with the **canonical status** badge (never
"Applied"). Filter by portal, status, and date range. Statuses are
**evidence-derived** — admins cannot hand-set a submission outcome; that integrity
rule is enforced server-side.

## Integrity & safety (what admins should know)
- **No fabricated data**: discovery is from real providers; statuses are
  evidence-gated. "Verified Submitted" requires application ID + confirmation URL +
  screenshot.
- **Suspending** a user blocks login immediately.
- **Rate limiting** protects login/register/search/apply (Redis-backed in prod,
  in-memory in dev).
- **PII**: resumes and any stored credentials are encrypted at rest with
  `CREDENTIAL_KEY`. **Never rotate `CREDENTIAL_KEY`** without a re-encryption plan —
  doing so makes existing encrypted data unreadable.

## Provider configuration (operator)
Discovery sources are gated by environment (see `INSTALLATION_GUIDE.md`):
- **Active without keys**: Remotive, Arbeitnow, Greenhouse, Lever, Ashby.
- **Keyed (gated)**: Adzuna, Jooble, JSearch, Workable.
- **Licensed-feed only (gated, off)**: Internshala, Wellfound.
A gated provider is inert until configured — it never breaks discovery and never
scrapes.

## Monitoring
- **Sentry** (`SENTRY_DSN`) for errors; **PostHog** (`POSTHOG_API_KEY`) for product
  events (signup, login, resume_uploaded, job_search, job_click, tracked_job,
  manual_apply, verified_submitted). Both are no-ops until their keys are set.
- Health: `GET /api/health` (liveness) and `GET /api/ready` (DB/cache/email status).
