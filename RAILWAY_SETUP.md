# Railway Production Setup — Jobora

Exact setup for the production stack: **API (Docker) + PostgreSQL + Redis + RQ
worker**, with **S3/R2** for object storage and a static-hosted frontend.

Repo artifacts used: `backend/Dockerfile`, `backend/entrypoint.sh` (migrations +
uvicorn on `$PORT`), `backend/railway.json`, `backend/Procfile`.

---

## Services to create in the Railway project

### A. PostgreSQL (plugin)
- Railway → **New → Database → PostgreSQL**.
- Exposes `DATABASE_URL` (reference it from the API + worker). Postgres URLs are
  auto-normalized to `postgresql+psycopg2://` in `config.py`.

### B. Redis (plugin)
- Railway → **New → Database → Redis**.
- Exposes `REDIS_URL` (rate limiting + job cache + RQ queue).

### C. API service (web)
- **New → GitHub Repo** → select this repo.
- **Settings → Root Directory:** `backend`  ← required (Dockerfile context).
- Build: Railway reads `backend/railway.json` → **Dockerfile** build,
  start `./entrypoint.sh`, healthcheck `/api/health`.
- Networking: **Generate Domain** (public URL for the API).
- Optional smaller image (no live browser): set build arg `INSTALL_BROWSERS=0`
  (only safe if you are NOT running live Greenhouse submission).

### D. Worker service (RQ) — recommended at >50 users
- **New → Empty Service** from the same repo, **Root Directory `backend`**,
  Dockerfile build.
- **Start command:** `rq worker submissions --url $REDIS_URL`
  (do NOT run migrations here — the web service owns them).
- Reference the same `DATABASE_URL`, `REDIS_URL`, `CREDENTIAL_KEY`, `S3_*`.
- For low volume you may skip this and keep `INPROCESS_WORKER=1` on the API.

### E. Frontend (separate host)
- `cd frontend && npm ci && npm run build` → deploy `dist/` to Vercel / Cloudflare
  Pages / Netlify.
- Set `VITE_API_BASE` to the API domain; add the frontend origin to `CORS_ORIGINS`.

---

## Shared environment (set on API + worker)
See `ENV_VARIABLES.md` for the full table. Minimum to boot in production:
`JOBORA_ENV=production`, `JWT_SECRET`, `CREDENTIAL_KEY`, `DATABASE_URL`,
`REDIS_URL`, `S3_BUCKET` (+ AWS creds), `ADMIN_EMAIL`, `ADMIN_PASSWORD`,
`CORS_ORIGINS`, `APP_BASE_URL`.

## Build/start summary
| Service | Build | Start | Migrations |
|---|---|---|---|
| API (web) | Dockerfile (`backend/`) | `./entrypoint.sh` | ✅ runs `alembic upgrade head` |
| Worker | Dockerfile (`backend/`) | `rq worker submissions --url $REDIS_URL` | ❌ (web owns it) |
| Frontend | `npm run build` | static host | — |

## Health
- Railway healthcheck: `GET /api/health` (in `railway.json`).
- Deep check: `GET /api/ready` → DB / cache / email / live_apply status.
