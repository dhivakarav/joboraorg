# Jobara — Production SaaS Implementation Roadmap

Target stack: **Next.js** (frontend) · **FastAPI** (backend) · **PostgreSQL** (DB) ·
**Redis** (cache + queue) · **Docker** (deploy). Built in phases. Phase 1 ships a
fully-functional product with **no paid AI dependency** — AI plugs in behind a
provider interface in Phase 3.

Design principle: every external dependency (DB, cache, email, AI) sits behind an
interface with a zero-config fallback, so the app runs locally without infra and
scales to managed Postgres/Redis/SMTP/Claude in production by setting env vars.

---

## Phase 1 — Production foundation (no paid APIs)

**1A. Infrastructure backbone**  ← *executed in this pass*
- [x] PostgreSQL-ready persistence (SQLAlchemy; `DATABASE_URL` selects SQLite ↔ Postgres)
- [x] Redis cache layer with in-memory fallback (`REDIS_URL`)
- [x] Email/notifications provider (SMTP ↔ console fallback)
- [x] Docker + docker-compose (api, db, redis, web) + `.env.example`
- [x] Health/readiness endpoints (`/api/health`, `/api/ready`)
- [x] Structured JSON logging + per-request IDs (`app/logging_config.py`)
- [x] Alembic migrations (`alembic/`; entrypoint runs `upgrade head`; SQLite dev still uses `create_all`)

**1B. Core features** (already implemented on FastAPI; carry forward unchanged)
- [x] JWT auth (register → admin approval → login), password reset
- [x] Resume management (upload, parse, structured profile, edit)
- [x] Real job aggregation (Greenhouse, Lever, Ashby, Workable, Remotive, Arbeitnow; Adzuna/Jooble with keys)
- [x] Job matching engine (0–100 score + reasons)
- [x] Application tracking (lifecycle: Saved→Applied→Submitted→Interview→Offer/Rejected)
- [x] Salary intelligence in INR (live FX with fallback)
- [x] Analytics dashboard stats
- [x] Adapter architecture for apply (auto vs manual)

**1C. Next.js frontend**  ← *next execution step*
- [ ] Next.js 15 App Router, Tailwind, server components where useful
- [ ] Port all pages: auth, dashboard, find-jobs, resume, filters, activity, settings, admin
- [ ] Production build, SEO-ready marketing/landing route

## Phase 2 — Scale & reliability
- Background job queue (Redis + RQ/Celery) for aggregation refresh + email sends
- Scheduled aggregation (warm the cache for popular queries)
- Rate limiting (Redis token bucket) + per-user quotas
- Observability: Sentry, structured JSON logs, Prometheus `/metrics`
- CI/CD, DB migrations in the deploy pipeline

## Phase 3 — AI layer (provider-gated, optional)
- Claude provider behind the existing `app/ai` interface (heuristic default)
- ATS score, resume suggestions, missing-skill detection, cover letters, career coach

## Phase 4 — Monetization
- Free/Pro plans, resume-review credits, premium feature gating, billing (Stripe)

---

## Deploy targets
- **Local/dev:** `docker compose up` (Postgres + Redis + API + Web)
- **Production:** managed Postgres (RDS/Neon/Supabase) + managed Redis (Upstash/ElastiCache) +
  containers on Fly.io / Render / ECS. Set `DATABASE_URL`, `REDIS_URL`, `SMTP_*`,
  `JWT_SECRET`, `CREDENTIAL_KEY`; optionally `ANTHROPIC_API_KEY` for Phase 3.
