# Jobara — Greenhouse Production Readiness Audit

Scope: the Greenhouse path + shared platform. Findings are code-cited and
severity-ranked. Audit only — nothing was changed.

Legend: **CRITICAL** = blocks any public exposure · **HIGH** = fix before beta ·
**MEDIUM** = fix during beta · **LOW** = post-beta polish.

---

## CRITICAL

**C1. Hardcoded secret fallbacks committed in the repo** — `config.py`
- `JWT_SECRET` defaults to `"change-me-in-prod-super-secret-key-jobora"`. If the
  env var is unset in prod, **anyone can forge admin JWTs**.
- `CREDENTIAL_KEY` has a **real Fernet key committed** (`emmG-…`). Portal
  credentials are encrypted with it — anyone with the repo can **decrypt every
  stored portal password**.
- Fix: refuse to boot if `JWT_SECRET`/`CREDENTIAL_KEY` are unset/default in
  non-dev; never commit a real key.

**C2. Hardcoded admin account** — `config.py` `ADMIN_EMAIL=<ADMIN_EMAIL>`,
`ADMIN_PASSWORD=<ADMIN_PASSWORD>`, seeded on every boot.
- A known, public admin credential = full takeover. Fix: require admin creds
  from env; force change on first login; don't ship a default password.

**C3. No rate limiting anywhere** — confirmed no limiter in `app/`.
- `/api/auth/login` is brute-forceable (no lockout/backoff).
- `/api/jobs/greenhouse/apply` launches a **full Chromium per call** with no cap
  — a few requests can exhaust RAM/CPU (DoS).
- `/api/jobs` fans out to external APIs per call (cost/abuse).
- Fix: Redis token-bucket per IP+user; strict caps on apply + login.

---

## HIGH

**H1. Live submission runs inline in the request** — `routers/jobs.py:331`
`await gh_apply(...)` launches a browser and blocks the request 10–30s. No queue,
no concurrency limit. At even modest concurrency this saturates the worker and
memory. → Move to a background worker (Redis + RQ/Celery) with a concurrency cap;
return a job id the UI polls.

**H2. JWT cannot be revoked / no logout server-side / 7-day life** —
`config.py:27`, `security.py`. A leaked token is valid for 7 days with no
denylist. → Shorter access token + refresh tokens, or a Redis revocation list;
invalidate on password change/suspend.

**H3. Uploads + evidence on local disk** — `uploads/`, `uploads/evidence/`.
Resume PDFs and confirmation screenshots are written to the container FS. Breaks
multi-replica/Fargate and is lost on redeploy. → S3 (or equivalent) with signed
URLs; this also unblocks horizontal scaling.

**H4. `applications.user_id` is not indexed** — `models.py`. Nearly every query
filters `Application.user_id` (dashboard, activity, dedupe) but only `id` and
`job_url_hash` are indexed → full table scans as data grows. → Add index on
`user_id` (and `(user_id, status)`).

**H5. No weak-password / signup hardening** — `routers/auth.py` register has **no
min-length** (only password-change enforces ≥6). Allows `password=a`. → Enforce a
real policy at register; add email verification before activation.

---

## MEDIUM

**M1. Duplicate-application race** — dedupe is a `query().first()` check in
`greenhouse_apply`, with **no `UniqueConstraint(user_id, job_url_hash)`**. Two
concurrent applies create duplicates. → Add the unique constraint + handle the
integrity error.

**M2. File-upload validation is shallow** — `routers/resume.py:24` checks
`content_type`/extension only; accepts `application/octet-stream`. No magic-byte
check, no malware scan. → Verify PDF magic bytes (`%PDF`), cap pages, consider AV
scanning; store outside any web-served path (already true).

**M3. Tokens passed in URLs** — SSE `/apply/stream?token=` and
`/evidence/screenshot?token=`. App logs only `request.url.path` (good — no leak
there), but tokens in URLs still leak via browser history, proxies, CDN access
logs. → Short-lived signed URLs for evidence; for SSE, a one-time stream ticket.

**M4. No global error handler / error envelope** — no `add_exception_handler`.
Unhandled errors return a bare 500; no correlation id surfaced to the client, no
error tracking. → Add a handler returning `{error, request_id}` and wire Sentry.

**M5. Resume PII stored unencrypted** — `resumes.raw_text` (full resume text) +
PDF on disk in cleartext. → Encrypt at rest or restrict access; add retention +
delete-my-data (GDPR/India DPDP).

**M6. N+1 in admin user list** — `routers/admin.py` runs a count query per user.
Fine at 100 users; fix with a `GROUP BY` join before growth.

**M7. Greenhouse robustness unproven on real confirmations** — success/ID regexes
and CAPTCHA handling validated against the **mock only**. → Validate against ≥5
real company confirmations before enabling live apply for users.

---

## LOW

- **L1.** `CORS allow_credentials=True` + `allow_methods=["*"]` — app uses Bearer
  tokens, not cookies, so credentials mode is unnecessary; tighten methods/headers.
- **L2.** Aggregator rate-limit state (`_provider_last_call`) is per-process —
  inaccurate across replicas; move to Redis with H1's work.
- **L3.** `submission_evidence` stores absolute local paths in JSON — brittle;
  store keys/relative refs once on S3 (H3).
- **L4.** No automated tests/CI — there's a manual E2E harness but no `pytest`
  suite or pipeline gating deploys.
- **L5.** Password-reset rows never pruned; expired tokens accumulate.

---

## What's already solid (don't redo)
- Bcrypt password hashing; reset tokens hashed + single-use + expiring; email
  enumeration protected.
- Alembic migrations; readiness probe (`/api/ready`); structured JSON logs with
  per-request `x-request-id`.
- Submission integrity: never fabricates answers; "Verified Submitted" requires
  confirmation + ID + screenshot; failures recorded, not faked.
- Dockerized, non-root container, healthcheck, migration-on-boot entrypoint.

---

# Roadmap → Public Beta (100 users)

Goal: 100 real users safely applying to **Greenhouse** jobs with their own
resumes. Lever/Internshala explicitly deferred.

### Phase B0 — Security gate (CRITICAL, ~must-do, days)
1. Boot-refuse on default/missing `JWT_SECRET` & `CREDENTIAL_KEY` (C1).
2. Env-driven admin creds + forced first-login password change (C2).
3. Redis rate limiting: login (per IP), apply (per user/day), search (C3).
4. Register password policy + email verification (H5).
**Exit:** no default secrets, no public admin password, brute force + apply abuse throttled.

### Phase B1 — Submission safety & scale (HIGH, ~1–2 wks)
5. Move `greenhouse/apply` to a **background queue** with concurrency cap + per-user/day limit; UI polls status (H1).
6. **S3** for resumes + evidence; signed URLs (H3, L3).
7. Index `applications.user_id`; add `UniqueConstraint(user_id, job_url_hash)` (H4, M1).
8. JWT refresh + revocation on password-change/suspend (H2).
**Exit:** apply can't exhaust the server; uploads durable; multi-replica safe.

### Phase B2 — Real-world Greenhouse hardening (HIGH/MEDIUM, ~1–2 wks)
9. Validate confirmation/ID detection on ≥5 real company boards; reCAPTCHA → Manual fallback verified (M7).
10. Pre-submit review screen that collects required screening answers (so auto-apply fires without fabrication).
11. Per-posting retry/backoff + clear failure surfaced in the Evidence view.
**Exit:** live Greenhouse apply works on real postings or honestly downgrades to Manual; users see truthful evidence.

### Phase B3 — Operability & trust (MEDIUM, ~1 wk)
12. Global error handler + **Sentry**; `/metrics` (Prometheus) (M4).
13. PII handling: encrypt/limit `raw_text`, add delete-my-data + retention (M5).
14. File-upload magic-byte validation (M2); short-lived evidence URLs (M3).
15. Postgres backups + restore drill; staging environment.
**Exit:** errors tracked, data-subject requests supported, backups proven.

### Phase B4 — Beta launch readiness (LOW + process, ~3–5 days)
16. `pytest` suite + CI gating deploys (run the E2E harness) (L4).
17. Tighten CORS (L1); prune reset tokens (L5).
18. Load test: 100 users, ~10 concurrent applies through the queue.
19. ToS/privacy policy; clear in-product consent that the user is submitting
    their **own** application; per-user daily apply cap visible in UI.
**Exit:** green CI, load target met, legal/consent in place → invite 100 users.

### Suggested order & sizing
```
B0 (blocking, ~3–5d) → B1 (~1–2w) → B2 (~1–2w) → B3 (~1w) → B4 (~3–5d)
≈ 5–7 weeks to a safe 100-user Greenhouse-only beta.
```
Do **not** start Lever/Internshala until B0–B2 are done — adding platforms now
multiplies the surface of every unresolved CRITICAL/HIGH issue.
