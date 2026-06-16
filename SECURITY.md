# Jobara — Security

This document covers the security model after **B0 (CRITICAL hardening)** and how
to deploy safely. Report vulnerabilities privately to the maintainer.

## Secrets policy (no committed secrets)
- **No secret values exist in the codebase.** `JWT_SECRET`, `CREDENTIAL_KEY`,
  `ADMIN_EMAIL`, `ADMIN_PASSWORD`, SMTP and provider keys come from the
  environment only.
- A set of **banned values** (old committed defaults, `changeme`, etc.) is
  rejected outright.
- **Production fail-closed:** with `JOBORA_ENV=production`, the app **refuses to
  start** unless `JWT_SECRET` and `CREDENTIAL_KEY` are present and valid
  (`CREDENTIAL_KEY` must be a real Fernet key). See `app/config.py`.
- **Development convenience:** with `JOBORA_ENV=development` (default), if those
  are unset the app generates **ephemeral per-process** keys and logs a loud
  warning. Ephemeral keys are not persisted and must never be used in prod.

Generate secrets:
```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"                       # JWT_SECRET
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # CREDENTIAL_KEY
```

## Admin bootstrap (no default account)
- There is **no hardcoded admin**. An admin is seeded **only** when `ADMIN_EMAIL`
  and `ADMIN_PASSWORD` are set; otherwise none is created (startup logs a notice).
- A seeded admin has `must_change_password=True`; the value is returned on login
  (`must_change_password`) and cleared when the password is changed
  (`PUT /api/profile/password`, min length 8).
- Rotate the bootstrap password immediately after first login.

## Rate limiting
Fixed-window limits (Redis-backed via the cache layer; in-memory fallback),
configurable via env:
| Action | Scope | Default |
|---|---|---|
| Login | per IP | `RL_LOGIN_PER_MIN=10` / min |
| Register | per IP | `RL_REGISTER_PER_HOUR=10` / hour |
| Greenhouse apply (burst) | per user | `RL_APPLY_BURST_PER_MIN=3` / min |
| Greenhouse apply (daily) | per user | `RL_APPLY_PER_DAY=30` / day |
| Job search | per user | `RL_SEARCH_PER_MIN=30` / min |
Exceeding a limit returns **HTTP 429** with `Retry-After`. Use a real `REDIS_URL`
in production so limits are shared across replicas. Toggle with `RATE_LIMIT_ENABLED`.

## Authentication & data protection (current state)
- Passwords hashed with **bcrypt**. Password reset tokens are **hashed,
  single-use, and expire** (`RESET_TOKEN_TTL_MINUTES`, default 30); reset
  responses are **email-enumeration safe**.
- Portal credentials are **Fernet-encrypted at rest** with `CREDENTIAL_KEY`.
- JWT (HS256). **Known limitation (tracked for B1):** tokens are not yet
  revocable and live `JWT_EXPIRE_MINUTES` (default 7 days). Refresh + revocation
  is the next hardening step.
- Submission evidence screenshots are owner-scoped; the screenshot endpoint
  authenticates via a `?token=` query param (loaded in `<img>`) — tracked for
  B1 replacement with short-lived signed URLs.

## Migration instructions
Schema is managed by **Alembic**. Three revisions exist (initial → submission
pipeline → must_change_password).
```bash
cd backend
export DATABASE_URL="postgresql+psycopg2://user:pass@host:5432/jobara"
alembic upgrade head      # apply all migrations
alembic current           # verify head
```
- Local SQLite dev auto-creates tables (`create_all`); production uses Alembic.
- The Docker image runs `alembic upgrade head` on boot via `entrypoint.sh`.
- After model changes: `alembic revision --autogenerate -m "msg"` → review → `upgrade head`.

## Deployment instructions (secure baseline)
1. **Set required env** (see `.env.example` / `.env.production.example`):
   `JOBORA_ENV=production`, `JWT_SECRET`, `CREDENTIAL_KEY`, `ADMIN_EMAIL`,
   `ADMIN_PASSWORD`, `DATABASE_URL`, `REDIS_URL`, `CORS_ORIGINS`, `APP_BASE_URL`,
   `SMTP_*`, `EXPOSE_RESET_TOKEN=0`.
2. **Provision** managed Postgres + Redis (Redis is required for shared rate
   limiting at scale).
3. **Deploy** the API container; `entrypoint.sh` migrates then starts uvicorn.
   The app will **refuse to boot** if secrets are missing — this is intended.
4. **First login** as the bootstrap admin → immediately change the password
   (clears `must_change_password`).
5. **Verify**: `GET /api/ready` shows `cache.backend=redis`, `database` ok; a
   handful of rapid `/api/auth/login` attempts return 429.
6. Terminate **TLS** at your load balancer/ingress; only expose the web service.
7. Store secrets in a secrets manager; **rotating `CREDENTIAL_KEY` invalidates
   stored portal credentials.**

## Still open (post-B0, by severity)
See `PRODUCTION_AUDIT.md`. HIGH items next: background queue for apply (H1), JWT
refresh/revocation (H2), S3 for uploads/evidence (H3), index `user_id` (H4),
signup password policy + email verification (H5).
