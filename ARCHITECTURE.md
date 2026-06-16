# Jobora — Architecture

System design **as implemented**. Jobora is a two-tier app: a **FastAPI** backend
(REST + background worker) and a **React (Vite)** single-page frontend, over a
SQL database with optional Redis + object storage.

## Tech stack
| Layer | Technology |
|---|---|
| Backend | FastAPI 0.115, SQLAlchemy 2.0, Pydantic v2, Alembic |
| DB | SQLite (dev) · PostgreSQL (prod) |
| Cache / queue | Redis (optional; in-memory fallback) · RQ worker |
| Storage | Local disk (dev) · S3 / Cloudflare R2 (prod) — resumes + evidence |
| Automation | Playwright (Chromium) — ATS form inspection / assisted-apply pipeline |
| Parsing | pdfplumber (resume text) |
| Auth | JWT (access + refresh + revocation), bcrypt |
| Monitoring | Sentry (errors) + PostHog (product events) — both gated |
| Frontend | React 18, Vite 5, React Router 6, TailwindCSS 3 |
| E2E | Playwright test runner (browser smoke suite) |

## High-level flow
```
Browser (React SPA)
   │  /api/* (JWT bearer)            Vite proxy in dev; same-origin or split-host in prod
   ▼
FastAPI app (app/main.py)
   ├── Routers: auth, resume, profile, filters, jobs, applications,
   │            apply, dashboard, admin, assisted, feedback
   ├── Job aggregator ──► Providers (real APIs/feeds, gated)
   ├── Eligibility + matching (pure, deterministic)
   ├── Adapters (apply): Greenhouse / Lever / Ashby / generic
   ├── Submission worker (in-process or RQ) ──► Playwright (live, opt-in)
   ├── Status engine (evidence-gated canonical statuses)
   └── Cross-cutting: cache, ratelimit, storage, security, analytics
   ▼
PostgreSQL  ·  Redis  ·  S3/R2  ·  SMTP  ·  Sentry/PostHog
```

## Backend layout (`backend/app/`)
| Module / package | Responsibility |
|---|---|
| `main.py` | App factory, router registration, lifespan (sqlite create_all + admin seed + worker start), Sentry init, health/ready. |
| `config.py` | Settings from env; **fail-closed** secrets in production. |
| `database.py` | Engine/session; `ensure_sqlite_columns()` for dev. |
| `models.py` | ORM: `User`, `Application`, `Resume`, `JobFilter`, `BetaInvite`, `Feedback`, `PasswordReset`. |
| `schemas.py` | Pydantic request/response models. |
| `routers/` | HTTP endpoints (see table below). |
| `jobs/` | `aggregator.py`, `matching.py`, `eligibility.py`, `currency.py`, `base.py` (RawJob/Provider), `providers/`. |
| `jobs/providers/` | One module per source (greenhouse, lever, ashby, remotive, arbeitnow, adzuna, jooble, jsearch, workable, internshala, wellfound). |
| `adapters/` | Apply layer per platform (greenhouse_*, lever_*, ashby_*, generic) + inspect/fill/submit pipelines. |
| `status.py` | Canonical `display_status` + `evidence_complete` — the single source of truth for what a status shows. |
| `services.py` | Profile assembly, resume materialization (decrypt → temp file). |
| `security.py` | Hashing, JWT, evidence tokens, Fernet encrypt/decrypt. |
| `storage.py` | Local/S3 abstraction for resumes + evidence. |
| `cache.py` / `ratelimit.py` | Redis-or-memory cache; fixed-window rate limiting. |
| `queue.py` | Submission worker (in-process async or RQ). |
| `analytics.py` | PostHog wrapper (gated, no-op without key). |
| `automation/engine.py` | "Scan & Track Matches" discovery+track runner. |
| `utils/resume_parser.py` | Heuristic PDF → profile fields. |

## API surface (routers)
| Prefix | Highlights |
|---|---|
| `/api/auth` | register, login, refresh, logout, me, verify-email, forgot/reset-password |
| `/api/resume` | upload (multipart), parsed (get/edit) |
| `/api/profile` | update, password |
| `/api/filters` | get/set role/location/keyword filters |
| `/api/jobs` | search (eligibility + internship filter), prepare, apply (Track), submit, assisted/{prepare,record}, sources |
| `/api/applications` | list (paginated), status, evidence (+ short-lived screenshot URL) |
| `/api/dashboard` | stats (canonical counts + recent activity) |
| `/api/feedback` | submit feedback/bug |
| `/api/admin` | stats, users (approve/suspend/details), applications, metrics, feedback, invites |
| `/api/apply` | scan-and-track stream (SSE) |
| `/api/health`, `/api/ready` | probes |

## Discovery pipeline
1. **Aggregator** (`jobs/aggregator.py`) fans out concurrently to every
   `available()` provider, with per-provider rate limiting + error isolation.
2. **Caching**: provider-level cache (query-keyed; query-agnostic board providers
   cached once) + aggregate result cache (TTL), so cold ~5.6s → repeat ~3ms.
3. **Normalize → filter → dedupe** (stable `RawJob.fingerprint`) → INR salary
   conversion.
4. Per job, the `/jobs` route **decorates** with `match_score`, **eligibility**
   (tier + reasons + early-career signal), platform/adapter capability, and
   `applied` state, then ranks eligibility-first and applies the internship filter.
5. **No scraping**: every provider uses an official API or licensed feed; gated
   providers return nothing until configured.

## Apply & status integrity
- **Greenhouse / generic → Track & Apply**: opens the official page, records
  **Tracked** via `/jobs/apply`. No auto-submission.
- **Lever / Ashby → Assisted Apply**: `assisted/prepare` returns a prefill packet
  (from the user's real profile) + required fields; the user completes captcha +
  submit on the real page; `assisted/record` stores evidence.
- **Status engine** (`status.py`): a row is **Verified Submitted only if**
  `application_id` + `confirmation_url` + a stored screenshot all exist; otherwise
  it downgrades to Submitted / Manual Apply / Tracked / Draft / Failed. The legacy
  **"Applied" label can never surface**. This invariant is enforced centrally and
  covered by tests.
- **Submission pipeline** (Playwright, opt-in via `JOBORA_LIVE`): validated G0–G3
  against controlled mocks; runs in the background worker; writes evidence to
  storage and a verified status only on a real confirmation.

## Data model (core)
- **User** — auth, status (pending/approved/suspended), seeker_type, plan field
  (unused), token_version (revocation), email-verify fields.
- **Application** — job snapshot + `status` (internal) + `submission_status`
  (canonical machine) + `application_id` + `confirmation_url` + `evidence_available`
  + `submission_evidence` (JSON) + `submitted_at`. `display_status` /
  `evidence_complete` are derived properties.
- **Resume** — encrypted file ref + parsed fields. **BetaInvite** — single-use code.
  **Feedback** — beta feedback/bugs.

## Security & privacy
Fail-closed secrets (prod won't boot without `JWT_SECRET`/`CREDENTIAL_KEY`); JWT
access+refresh with `token_version` revocation; bcrypt passwords; **PII encryption
at rest** (resume bytes + parsed text, Fernet); short-lived signed evidence URLs;
admin-approval gate; Redis-backed rate limiting; CORS allow-list; robots-respecting
providers.

## Frontend (`frontend/src/`)
- **Routing** (`App.jsx`): public (`/login`, `/register`, `/pending`, password
  reset); user (`/app/{dashboard,jobs,resume,filters,activity,verification,
  settings}`); admin (`/admin/{dashboard,users,applications,operations}`). Guards:
  `RequireUser` / `RequireAdmin`.
- **Shell** (`components/Layout.jsx`): responsive sidebar (desktop) + drawer
  (mobile); global feedback widget; onboarding modal.
- **State**: `AuthContext` (JWT in `localStorage`, `/auth/me`); a thin `api` client
  (`api/client.js`) attaches the bearer token and normalizes errors.
- **Key components**: `AssistedApplyWizard`, `EvidenceModal`, `FeedbackWidget`,
  `HowItWorks`, `UI.jsx` (StatusBadge, Skeleton, Modal, Toast, etc.).

## Deployment shape (documented, not run here)
Docker image (backend) + static frontend; Postgres + Redis + S3/R2; migrations
auto-apply on boot; optional separate RQ worker. See `DEPLOYMENT_GUIDE.md` /
`RAILWAY_SETUP.md` / `DEPLOY_CHECKLIST.md`.
