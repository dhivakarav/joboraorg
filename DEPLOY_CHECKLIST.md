# Deploy Checklist — Jobora

Run top to bottom. ☐ = do it, ☑ = verify.

## 0. Pre-deploy (local)
- [ ] `cd backend && .venv/bin/python -m pytest -q` → **21 passed**.
- [ ] `cd frontend && npm run build` → clean.
- [ ] Commit + push to the deploy branch.

## 1. Provision (Railway)
- [ ] Create project; add **PostgreSQL** + **Redis** plugins.
- [ ] Create **API** service from repo; **Root Directory = `backend`**; Generate Domain.
- [ ] (≥50 users) Create **worker** service; start `rq worker submissions --url $REDIS_URL`;
      set `INPROCESS_WORKER=0` on the API.

## 2. Object storage
- [ ] Create bucket (S3 or R2); create access key/secret.
- [ ] Enable **versioning** (S3) / lifecycle (R2) for evidence + resumes.

## 3. Environment (see ENV_VARIABLES.md)
- [ ] Generate `JWT_SECRET` + `CREDENTIAL_KEY`; store `CREDENTIAL_KEY` in a vault.
- [ ] Set all **Required** vars on API (+ worker).
- [ ] Set **SMTP_*** (real email).
- [ ] Set `SENTRY_DSN`, `POSTHOG_API_KEY`.
- [ ] Set `BETA_INVITE_REQUIRED=1`, `EXPOSE_RESET_TOKEN=0`, `CORS_ORIGINS`, `APP_BASE_URL`.

## 4. PostgreSQL migration checklist
- The web service runs **`alembic upgrade head`** automatically on boot
  (`entrypoint.sh`). Expected head: **`c3d4e5f6a7b8`** (beta_invites + feedback).
- Migration chain (linear):
  `41df8728e658 → 0f9d269f834a → 0ec9a06a5084 → ef54e06ed042 → 71c6a7cbcb4e →
   a1b2c3d4e5f6 (integrity status) → b2c3d4e5f6a7 (plan fields) → c3d4e5f6a7b8`.
- [ ] After first deploy, check logs: `Applying database migrations…` then no errors.
- [ ] Verify head: `railway run alembic current` → ends with `c3d4e5f6a7b8 (head)`.
- [ ] Confirm tables exist: `users, applications, beta_invites, feedback,
      portal_credentials, resumes, job_filters, password_resets`.
- [ ] **Do not** run `create_all` against Postgres — Alembic owns the prod schema
      (only SQLite dev uses `create_all`).

## 5. Redis
- [ ] `REDIS_URL` referenced by API (+ worker).
- [ ] `GET /api/ready` shows `cache.backend = redis` (not `memory`). If `memory`,
      `REDIS_URL` isn't wired — fix before launch (limits won't be shared).

## 6. SMTP
- [ ] Send a test: register a throwaway account → confirm the verification +
      "pending approval" emails arrive (not just console logs).

## 7. Deploy commands
```bash
# Railway CLI (optional; the GitHub integration also auto-deploys on push)
railway up                       # build + deploy current service
railway run alembic current      # verify migration head
railway run alembic upgrade head # (manual migrate if you disabled auto)
railway logs                     # watch boot + healthcheck
```

## 8. Post-deploy smoke test
- [ ] `GET /api/health` → `{"status":"ok"}`.
- [ ] `GET /api/ready` → database ok, cache `redis`, email `smtp`.
- [ ] Log in as admin (`ADMIN_EMAIL`/`ADMIN_PASSWORD`); change password.
- [ ] `POST /api/admin/invites?count=15` → codes returned.
- [ ] Register with a code → approve → login → upload resume → Find Jobs returns
      results → track a job → Activity Log shows **Tracked** (never "Applied").
- [ ] Submit a feedback + a bug via the widget → appears in `/api/admin/feedback`.
- [ ] Confirm a PostHog event (e.g. `signup`) lands; trigger a test Sentry error.

## 9. Go / No-go
- [ ] All of §8 pass, `cache.backend=redis`, email delivers, migration head correct,
      0 high-severity errors in Sentry → **invite Wave 1 (10 users).**
