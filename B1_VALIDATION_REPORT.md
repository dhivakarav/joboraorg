# B1 Validation Report — HIGH-priority findings

Phase B1 closes the HIGH findings from `PRODUCTION_AUDIT.md` (scalability +
reliability). No new job platforms were added. All results below were executed.

## Summary: HIGH findings status

| Finding | Status | How |
|---|---|---|
| **H1** Inline browser submission | ✅ Closed | Background queue + concurrency cap + retry |
| **H2** No JWT revocation / long life | ✅ Closed | Short access + refresh tokens, `token_version` revocation |
| **H3** Local-disk uploads/evidence | ✅ Closed | Storage abstraction (local default, S3-compatible) |
| **H4** `user_id` not indexed / N+1 | ✅ Closed | Indexes + grouped admin count query |
| **H5** No signup policy / email verify | ✅ Closed | Password policy + email-verification flow |

---

## H1 — Background submission queue
- `POST /api/jobs/greenhouse/apply` now **enqueues** and returns immediately; the
  browser runs in a worker (`app/queue.py`). Statuses: `Queued → Processing →
  Verified Submitted/…`.
- **No browser per request** — verified enqueue latency (below).
- **Concurrency cap** via semaphore (`SUBMISSION_CONCURRENCY`, default 2).
- **Retry** of transient failures (timeouts/connection/`net::`) up to
  `SUBMISSION_MAX_ATTEMPTS` with backoff; CAPTCHA/validation never retried.
- **Redis-backed mode**: when `REDIS_URL` is set, jobs enqueue to an RQ
  "submissions" queue consumed by a separate `rq worker` (concurrency = #workers).
  In-process worker is the dev/single-node default.

Verified:
- Apply returned **Queued** in ~**3 ms p50 / 46 ms p95** (was 10–30 s inline).
- Worker processed to **Verified Submitted** with an application id + screenshot.
- 12 enqueued jobs all completed with concurrency=2.
- Retry log: `app 1 transient failure (attempt 1); retrying` → terminal `Failed`
  after max attempts. CAPTCHA path → `CAPTCHA Required` (no retry, no false success).

## H2 — JWT refresh + revocation
- Login issues a short-lived **access token** (`ACCESS_TOKEN_MINUTES`, default 60)
  + a **refresh token** (`REFRESH_TOKEN_DAYS`, default 7), both carrying a
  per-user `token_version`.
- `POST /api/auth/refresh` exchanges a refresh token for a new pair.
- `POST /api/auth/logout` bumps `token_version` → **all** existing tokens invalid.
- Password change and admin **suspend** also bump `token_version`.
Verified: `/me` works with access → after `logout`, the same access token → **401**,
and the old refresh token → **401**.

## H3 — S3-compatible storage
- `app/storage.py` facade: `save_bytes/save_file/open_bytes/local_path/url`.
  Backend is **local** by default, **S3** when `S3_BUCKET` (+ creds) is set
  (AWS/MinIO/R2 via boto3, presigned URLs). Resume uploads and evidence
  screenshots/HTML go through it; `local_path()` keeps a readable path for
  pdfplumber and file serving.
- Verified on the **local** backend (resume stored under a storage key, parsed,
  served; evidence uploaded post-submission). The S3 backend is implemented and
  gated; it was **not** exercised against a live bucket in this environment.

## H4 — DB performance
- Indexes added (migration): `applications.user_id`, `applications.submission_status`,
  composite `(user_id, status)` and `(user_id, submission_status)`.
- Admin user list rewritten from **N+1** (one count per user) to a **single
  grouped query**.
Verified: `/api/admin/users` with ~61 users returns in **~3 ms p50**.

## H5 — Signup policy + email verification
- Register enforces **≥8 chars with letters and digits** (weak/no-digit → 400).
- Email verification: a hashed, 24h token is issued on register and emailed
  (console fallback); `POST /api/auth/verify-email` confirms it. A login gate is
  available via `REQUIRE_EMAIL_VERIFICATION` (**off by default** so the existing
  admin-approval flow is unchanged until you enable it).
Verified: weak passwords rejected; strong accepted.

---

# Performance Benchmarks
(single uvicorn worker, SQLite, local Chromium; indicative, not tuned hardware)

| Metric | Result |
|---|---|
| Apply **enqueue** latency | p50 **3 ms**, p95 **46 ms** (browser excluded from request) |
| Submission throughput (concurrency=2, real Chromium each) | 12 jobs in **21.3 s** ≈ **0.56 submissions/s** |
| Admin user list (~61 users) | **~3 ms** p50 (N+1 removed) |

The apply latency drop (tens of seconds → single-digit ms) is the core
reliability/scalability win: the API no longer blocks on a browser, and browser
count is bounded by the concurrency cap regardless of request volume.

# Load Test Results
Concurrent authenticated reads of `GET /api/applications` (DB-bound, exercises
the new `user_id` index), 200 requests per run:

| Concurrency | Success | p50 | p95 | p99 | Throughput |
|---|---|---|---|---|---|
| 10 | 200/200 | 32 ms | 41 ms | 43 ms | ~322 req/s |
| 25 | 200/200 | 90 ms | 130 ms | 162 ms | ~270 req/s |
| 50 | 200/200 | 149 ms | 251 ms | 354 ms | ~313 req/s |

100% success at all levels. (SQLite + single worker is the dev ceiling; with
Postgres + Redis + multiple replicas these numbers scale out — that's why H3/H1
were built backend-agnostic.)

---

## Honest scope notes
- **Redis/RQ and S3** paths are implemented and config-gated but were validated
  with their **fallbacks** (in-process worker, local storage) since this
  environment has no Redis/S3. Wiring is in place; flip env vars in prod.
- **Email verification** is implemented but gated **off** by default
  (`REQUIRE_EMAIL_VERIFICATION=0`).
- Load numbers reflect SQLite + one worker; treat as a lower bound.

## New/changed config (see `.env.example`)
`SUBMISSION_CONCURRENCY`, `SUBMISSION_MAX_ATTEMPTS`, `SUBMISSION_RETRY_DELAY`,
`INPROCESS_WORKER`, `ACCESS_TOKEN_MINUTES`, `REFRESH_TOKEN_DAYS`,
`REQUIRE_EMAIL_VERIFICATION`, `S3_BUCKET`/`S3_ENDPOINT_URL`/`S3_REGION`.

## Migration
One new revision `ef54e06ed042` (4-revision chain total). Applies cleanly:
`alembic upgrade head`.

## Remaining (MEDIUM, Phase B2)
Per `PRODUCTION_AUDIT.md`: M2 magic-byte upload check (partially added), M3
short-lived evidence URLs, M4 global error handler + Sentry, M5 PII encryption,
M7 real-Greenhouse confirmation validation, plus CI/tests.
