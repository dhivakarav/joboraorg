# Jobara — Public Beta Readiness Report

After B0 (CRITICAL) + B1 (HIGH) + B2 (MEDIUM). Greenhouse only — no other
platforms enabled. This report states what's done, what's verified, the honest
gaps, scaling estimates, and the target deployment architecture.

## B2 completion (MEDIUM findings)

| # | Item | Status | Evidence |
|---|---|---|---|
| 1 | Global error handling | ✅ | All errors return `{error, request_id}`; unhandled → 500 with no traceback leak; tested |
| 2 | Sentry integration | ✅ (gated) | Initializes when `SENTRY_DSN` set; no-op otherwise |
| 3 | Real Greenhouse confirmation validation | ⚠️ Hardened + unit-tested; **not** run against a live real submission | `classify_confirmation()` + 5 tests incl. real GH phrasings |
| 4 | Short-lived evidence URLs | ✅ | Evidence-scoped token (TTL `EVIDENCE_URL_TTL`), S3 presigned path; wrong-app → 401; fetch 200 |
| 5 | Resume / PII encryption | ✅ | Resume Fernet-encrypted at rest (`JBENC1:`), worker decrypts to temp; `raw_text` encrypted |
| 6 | CI/CD pipeline | ✅ | `.github/workflows/ci.yml`: tests + migrations + frontend + docker builds |
| 7 | Automated tests | ✅ | `backend/tests/` — **15 passing** (auth, refresh/revoke, rate limit, policy, detection, crypto, envelope) |

### The one honest caveat (priority #3)
The submit→confirm→extract pipeline and the confirmation detector are validated
against a **controlled mock** and **unit fixtures with real Greenhouse phrasings**
— never against a live submission to a real employer (that would file a fake
application). Two real-world facts are baked in: (a) real Greenhouse often shows
**no application id** to the applicant, so the honest outcome there is
**"Submitted"** (confirmation detected) not "Verified Submitted"; (b) reCAPTCHA
postings correctly fall back to failure/manual. **Before users rely on
auto-submit, run it against a small set of real postings using a real
volunteer's genuine application.** Until then, "Manual Apply Required" is the
honest default.

---

## Readiness by scale

### ✅ 100 users — Ready (with the #3 caveat)
- Security (B0), reliability/queue (B1), and ops/PII (B2) are in place.
- **Setup:** 1 API instance + 1 worker, managed Postgres (small), managed Redis,
  S3. In-process worker is fine, but prefer a separate RQ worker so a stuck
  browser never affects the API.
- **Bottleneck:** browser submission throughput (~0.5 submissions/s at
  concurrency 2). At 100 users this is comfortably enough with the daily caps.
- **Do first:** real-posting validation (#3); set `REQUIRE_EMAIL_VERIFICATION=1`;
  add a Sentry DSN.

### 🟡 1,000 users — Needs the scale-out wiring (mostly built, not yet exercised)
- **Move to Redis/RQ workers** (already coded): run N worker replicas; concurrency
  = replicas × `SUBMISSION_CONCURRENCY`. Browser submission is the cost/throughput
  driver — size the worker fleet to demand and the daily caps.
- **Postgres**: connection pooling (PgBouncer), tuned indexes (done), watch slow
  queries; consider a read replica for analytics.
- **Redis** is now load-bearing (cache + rate limit + queue) — make it HA.
- **Observability**: Sentry + a metrics dashboard (`/metrics` is a fast-follow),
  queue-depth alerts.
- **Not yet exercised** at this level here (load tests were SQLite/single-node);
  run a staged load test on the real stack.

### 🔴 10,000 users — Requires a dedicated phase (B3+)
- **Browser farm**: a horizontally-autoscaled worker pool (or a managed browser
  service); per-submission cost and anti-bot blocking become first-order
  concerns. Expect a meaningful fraction of postings to require manual fallback.
- **DB**: Postgres with PgBouncer + read replicas (or a managed scaler);
  partition/retain `applications` + evidence.
- **Queue**: backpressure, dead-letter queue, priority lanes; idempotency on
  enqueue (the `(user_id, job_url_hash)` upsert helps).
- **Multi-region** API/CDN; S3 lifecycle policies for evidence retention.
- **Legal/ToS at scale**: automated submission volume needs review per platform;
  this is a product/legal gate, not just engineering.

---

## Deployment architecture — Vercel + Railway/Render + PostgreSQL + S3

```
                    ┌──────────────────────────┐
   Browser ───────▶ │  Vercel (frontend)        │   static Vite SPA build
                    │  VITE_API_BASE_URL ───────┼────────────┐
                    └──────────────────────────┘             │ HTTPS
                                                              ▼
                    ┌───────────────────────────────────────────────────┐
                    │  Railway/Render                                    │
                    │                                                    │
                    │  ┌─────────────┐        ┌──────────────────────┐  │
                    │  │ API service │        │ Worker service        │  │
                    │  │ FastAPI     │  RQ    │ rq worker "submissions"│ │
                    │  │ (Docker)    │ ─────▶ │ JOBORA_LIVE=1 +        │  │
                    │  │ migrates on │        │ Playwright Chromium    │  │
                    │  │ boot        │        │ (INSTALL_BROWSERS=1)   │  │
                    │  └─────┬───────┘        └──────────┬────────────┘  │
                    └────────┼───────────────────────────┼──────────────┘
                             │                            │
              ┌──────────────┼───────────┬───────────────┼───────────┐
              ▼              ▼            ▼               ▼           ▼
     ┌──────────────┐ ┌──────────┐ ┌──────────┐   (resumes +    (presigned
     │ PostgreSQL   │ │  Redis   │ │   S3 /   │    evidence)      GET URLs)
     │ (managed)    │ │ (managed)│ │   R2     │
     │ Neon/Railway │ │ Upstash  │ │ bucket   │
     └──────────────┘ └──────────┘ └──────────┘
       schema via       cache +       PII at rest (resumes encrypted
       Alembic          rate-limit    before upload) + confirmation
                        + RQ queue    screenshots
```

**Service config**
- **Vercel (frontend):** build `frontend` (Vite). Env `VITE_API_BASE_URL=https://<api-domain>/api`. (Note: current frontend is React+Vite served static — Vercel hosts it directly; a Next.js port would also deploy here.)
- **API (Railway/Render):** `backend/Dockerfile` (build arg `INSTALL_BROWSERS=0` — API doesn't need a browser). `entrypoint.sh` runs `alembic upgrade head`. Env: `JOBORA_ENV=production`, `JWT_SECRET`, `CREDENTIAL_KEY`, `ADMIN_EMAIL/PASSWORD`, `DATABASE_URL`, `REDIS_URL`, `CORS_ORIGINS=https://<vercel-domain>`, `APP_BASE_URL`, `S3_BUCKET`(+creds), `SMTP_*`, `EXPOSE_RESET_TOKEN=0`, `SENTRY_DSN`, `REQUIRE_EMAIL_VERIFICATION=1`, `INPROCESS_WORKER=0`.
- **Worker (Railway/Render):** same image **with `INSTALL_BROWSERS=1`**, command `rq worker submissions`, env `JOBORA_LIVE=1`, `REDIS_URL`, `DATABASE_URL`, `CREDENTIAL_KEY`, `S3_*`. Scale replicas for throughput.
- **PostgreSQL:** Neon / Railway / Render managed; backups on.
- **Redis:** Upstash / Railway / Render; used by cache, rate limiting, and RQ.
- **S3/R2:** `S3_BUCKET` (+ `S3_ENDPOINT_URL` for R2/MinIO); evidence served via presigned URLs.

**render.yaml** already provisions DB+Redis+API+web; add a `worker` service
(`rq worker submissions`, browsers installed) and an S3 bucket for the full
production topology.

---

## Go / No-go for 100-user beta
**GO**, conditional on three quick items:
1. Validate Greenhouse auto-submit on ≥5 **real** postings with a volunteer's
   genuine application (#3) — otherwise keep auto-submit off and ship Manual Apply.
2. Provision managed Postgres + Redis + S3 and a separate RQ worker; set all
   production env (fail-closed config enforces the secrets).
3. Turn on `SENTRY_DSN` + `REQUIRE_EMAIL_VERIFICATION`, and load-test the real
   stack once.

Everything else (auth, rate limiting, queue, encryption, evidence, error
handling, CI, tests) is in place and verified.
