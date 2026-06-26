# Jobora — Deployment Checklist (Render)

Production deploys from the **`main`** branch via the `render.yaml` Blueprint.
This file documents everything needed to provision and verify a deployment.

> **Never commit secrets.** All keys/passwords below are set in the Render
> dashboard (or your own `.env`, which is gitignored). This file contains
> **no secret values** — only how to generate/set them.

---

## 1. Required Render services

The `render.yaml` Blueprint provisions all four automatically:

| Service | `render.yaml` name | Type | Plan | Notes |
|---|---|---|---|---|
| PostgreSQL | `jobara-db` | `database` | free | App datastore (Postgres 16). Free DB expires ~90 days. |
| Redis | `jobara-redis` | `keyvalue` | free | Shared cache / queue. Only reachable from Render services. |
| FastAPI backend | `jobara-api` | `web` (docker) | free | Cold-starts after ~15 min idle on free. Bump to `starter` for always-on. |
| React frontend | `jobara-web` | `web` (static) | free | Vite build, SPA rewrite to `index.html`. |

Deploy: **render.com → New → Blueprint → select `dhivakarav/jobora` (branch `main`)**.

---

## 2. Environment variables

### `jobara-api` (backend)

| Var | Required | How to set | Notes |
|---|---|---|---|
| `DATABASE_URL` | ✅ | auto (from `jobara-db`) | `postgres://` is auto-normalized to `postgresql://`. |
| `REDIS_URL` | ✅ | auto (from `jobara-redis`) | Shared cache; enables multi-replica scaling. |
| `JWT_SECRET` | ✅ | auto (`generateValue`) | Or generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `CREDENTIAL_KEY` | ✅ | **manual** (`sync:false`) | Fernet key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. **Rotating it invalidates stored portal credentials.** |
| `CORS_ORIGINS` | ✅ | **manual** | Comma-separated allowed browser origins, e.g. `https://jobara-web.onrender.com`. Must include every frontend origin. |
| `APP_BASE_URL` | ✅ | **manual** | Public frontend URL (used in emails/links). |
| `ADMIN_EMAIL` | ✅ (first run) | **manual** | Bootstraps the admin. If unset → no admin seeded. |
| `ADMIN_PASSWORD` | ✅ (first run) | **manual** | Seeded admin is flagged `must_change_password`. |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM` / `SMTP_TLS` | ⚠️ prod | **manual** | Needed for verification / password-reset emails. |
| `EXPOSE_RESET_TOKEN` | default `0` | preset | Keep `0` in prod (don't leak reset tokens in API responses). |
| `LOG_LEVEL` | default `INFO` | preset | |

**Optional** (widen coverage / enable features): `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`,
`JOOBLE_API_KEY`, `GREENHOUSE_BOARDS`, `LEVER_COMPANIES`, `ANTHROPIC_API_KEY`,
`AI_MODEL`, `RAZORPAY_KEY_ID`/`RAZORPAY_KEY_SECRET`/`RAZORPAY_WEBHOOK_SECRET`,
`SENTRY_DSN`, `POSTHOG_API_KEY`/`POSTHOG_HOST`, and tuning vars
(`JOB_CACHE_TTL`, `PROVIDER_TIMEOUT`, `PROVIDER_MIN_INTERVAL`, rate-limit `RL_*`).
Full list: see `.env.production.example`.

### `jobara-web` (frontend)

| Var | Required | Notes |
|---|---|---|
| `VITE_API_BASE_URL` | ✅ | Backend API base, **must end with `/api`**, e.g. `https://jobara-api.onrender.com/api`. Baked in at build time. |

---

## 3. Build commands

- **Backend (`jobara-api`):** Docker — `dockerfilePath: ./backend/Dockerfile`,
  `dockerContext: ./backend`. No separate build command (image build installs
  `requirements.txt` + Playwright Chromium for live automation).
- **Frontend (`jobara-web`):** `cd frontend && npm ci && npm run build`
  → publishes `./frontend/dist`.

---

## 4. Start command

- **Backend:** container `CMD ["./entrypoint.sh"]` →
  ```sh
  alembic upgrade head
  uvicorn app.main:app --host 0.0.0.0 --port $PORT
  ```
  (`$PORT` is injected by Render.)
- **Frontend:** static site — no start command; served by Render's CDN with an
  SPA rewrite (`/* → /index.html`).

---

## 5. Database migration process

- Migrations are **applied automatically on every deploy** by `entrypoint.sh`
  (`alembic upgrade head`) before the server starts.
- Current head revision: **`f6a7b8c9d0e1`**.
- Local SQLite dev creates tables directly (`create_all`); **Postgres in
  production is managed by Alembic only** — never `create_all`.
- Manual run (if ever needed): `alembic upgrade head` from `backend/` with
  `DATABASE_URL` set.

---

## 6. Health check endpoint

- **`GET /api/health`** → `200` when the API is up (used by Render's
  `healthCheckPath` and the Docker `HEALTHCHECK`).

---

## 7. Common deployment issues

| Symptom | Cause / Fix |
|---|---|
| First request after idle is slow / 502 | Free-plan **cold start** (~15 min idle spin-down). Upgrade `jobara-api` to `starter` for always-on. |
| Login works but app calls fail with CORS errors | `CORS_ORIGINS` doesn't include the exact frontend origin (scheme + host). Add it, redeploy API. |
| Frontend can't reach API / 404 on calls | `VITE_API_BASE_URL` missing `/api` suffix, or set after build (it's **build-time** — rebuild the web service after changing). |
| "This email is not registered" for admin | `ADMIN_EMAIL`/`ADMIN_PASSWORD` not set → no admin seeded. Set both, redeploy. |
| Stored portal credentials suddenly invalid | `CREDENTIAL_KEY` was rotated. Keep it stable; rotating requires users to re-enter portal creds. |
| DB connection errors with `postgres://` | Handled automatically (normalized to `postgresql://`), but verify `DATABASE_URL` is the **internal** connection string. |
| Postgres unavailable after ~90 days | Free Render Postgres expires. Upgrade the DB plan before then. |
| Slow/failed image build | The image installs Playwright Chromium (needed for live auto-apply). Free tier is tight; `starter` builds more reliably. |
| Password-reset / verification emails not arriving | `SMTP_*` not configured. Set them; keep `EXPOSE_RESET_TOKEN=0`. |

---

## 8. Post-deployment verification

- [ ] `GET https://<api-host>/api/health` returns `200`.
- [ ] Render API logs show `alembic upgrade head` ran and `Application startup complete`.
- [ ] Frontend URL loads (no console errors).
- [ ] Log in as the seeded admin (`ADMIN_EMAIL` / `ADMIN_PASSWORD`) → lands on `/admin/dashboard`; complete the forced password change.
- [ ] Register a normal user → email verification flow works (SMTP configured).
- [ ] Job search returns results; an application can be tracked.
- [ ] No CORS errors in the browser console for API calls.
- [ ] `CREDENTIAL_KEY`, `JWT_SECRET`, `ADMIN_PASSWORD`, SMTP creds are set in the dashboard — **not** in any committed file.
- [ ] `git ls-files | grep -E '\.env$'` returns nothing (only `*.example` templates tracked).
