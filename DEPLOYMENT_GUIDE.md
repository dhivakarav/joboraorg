# Jobora — Deployment Guide (Railway)

Production stack: **FastAPI (Docker) + PostgreSQL + Redis + S3/R2 object storage**,
with a separate **submission worker**. Frontend (Vite build) on any static host
(Vercel/Netlify/Cloudflare Pages) or served behind the same domain.

> Migrations run automatically on deploy: `entrypoint.sh` executes
> `alembic upgrade head` before starting uvicorn. The server **refuses to start**
> in production without `JWT_SECRET` + `CREDENTIAL_KEY`.

---

## 1. Provision on Railway
1. **New Project → Deploy from GitHub repo.**
2. Add the **API service**:
   - Set **Root Directory = `backend/`** (so the Dockerfile context is correct).
   - Railway auto-detects `backend/railway.json` (Dockerfile build, healthcheck
     `/api/health`, `./entrypoint.sh` start). The app binds to `$PORT` (injected).
3. Add **PostgreSQL** plugin → exposes `DATABASE_URL`. (Postgres URLs are
   auto-normalized to `postgresql+psycopg2://`.)
4. Add **Redis** plugin → exposes `REDIS_URL` (shared rate-limit + job cache + queue).
5. Add a second service for the **worker** (same image / root dir), start command:
   `python -m app.worker` *(or run the in-process worker by leaving
   `INPROCESS_WORKER=1` on the API for low volume)*.

## 2. Object storage (S3 / Cloudflare R2)
Resumes (encrypted) + confirmation evidence must persist across deploys/replicas.
- Create a bucket (AWS S3 or **R2**).
- Set: `S3_BUCKET`, `S3_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`.
- For **R2/MinIO** also set `S3_ENDPOINT_URL`.
- Empty `S3_BUCKET` → local disk (dev only; **not** safe on Railway's ephemeral FS).

## 3. Production environment variables (checklist)
| Var | Required | Notes |
|---|---|---|
| `JOBORA_ENV=production` | ✅ | Enables fail-closed secret checks |
| `JWT_SECRET` | ✅ | `python -c "import secrets;print(secrets.token_urlsafe(48))"` |
| `CREDENTIAL_KEY` | ✅ | `python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"` |
| `DATABASE_URL` | ✅ | from Railway Postgres |
| `REDIS_URL` | ✅ | from Railway Redis |
| `S3_BUCKET` + AWS creds | ✅ | resumes + evidence |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | ✅ (first run) | seeds the admin; change on first login |
| `CORS_ORIGINS` | ✅ | your web app origin(s), e.g. `https://app.jobora.com` |
| `APP_BASE_URL` | ✅ | public URL (email links) |
| `SMTP_*` | ⚠️ | real email; console fallback if unset |
| `SENTRY_DSN` | ⚠️ | error tracking |
| `POSTHOG_API_KEY` | ⚠️ | product analytics |
| `BETA_INVITE_REQUIRED=1` | ⚠️ | gate signups to invited users |
| `RATE_LIMIT_ENABLED=1` | default | Redis-backed limits |
| `JOBORA_LIVE` | optional | leave `0` unless live Greenhouse submission is enabled |

## 4. Frontend
`cd frontend && npm ci && npm run build` → deploy `dist/` to a static host. Set the
API base URL (`VITE_API_BASE`) to the Railway API domain, and add that static
origin to `CORS_ORIGINS`.

## 5. Health & readiness
- **`GET /api/health`** → `{"status":"ok"}` (liveness; used by Railway healthcheck).
- **`GET /api/ready`** → per-subsystem status (DB, cache backend, email, AI,
  live_apply). Use for dashboards / deploy gates.

## 6. Backups
- **Postgres:** enable Railway's managed backups (daily); for extra safety run a
  scheduled `pg_dump "$DATABASE_URL" | gzip > backup-$(date +%F).sql.gz` to the
  bucket. Test a restore before launch.
- **Object storage:** enable bucket versioning (S3) / object lifecycle on R2.
- **Secrets:** store `JWT_SECRET` / `CREDENTIAL_KEY` in a password manager —
  losing `CREDENTIAL_KEY` makes encrypted resumes/credentials unrecoverable.

## 7. First-deploy smoke test
1. `GET /api/health` → ok; `GET /api/ready` → database ok, cache `redis`.
2. Register → admin approves → login.
3. Upload a resume → Find Jobs returns results → track a job → it appears in
   Activity Log as **Tracked** (not "Applied").
4. (If invites on) generate codes via `POST /api/admin/invites`.
