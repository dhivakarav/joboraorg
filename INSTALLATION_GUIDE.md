# Jobora — Installation Guide

Local/dev setup of the current system **as implemented**. (For production
infrastructure, see `DEPLOYMENT_GUIDE.md` / `RAILWAY_SETUP.md`.)

## Prerequisites
- **Python 3.9+** (3.11 in the Docker image)
- **Node.js 18+** (Node 24 used for the Playwright E2E suite)
- Optional: **Redis** (rate-limit/cache/queue), **PostgreSQL** (prod DB), an
  **S3/R2** bucket (prod storage). Dev runs without any of these.

## 1. Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Optional (only for live ATS automation / Greenhouse inspection):
playwright install chromium
```

### Configure
Copy `.env.example` → `.env` and fill what you need. **Dev requires nothing**
(ephemeral secrets are auto-generated); **production REFUSES to start** without
`JWT_SECRET` and `CREDENTIAL_KEY`.

Generate secrets:
```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"                 # JWT_SECRET
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # CREDENTIAL_KEY
```

Key environment variables (full list in `.env.example` / `ENV_VARIABLES.md`):
| Var | Dev | Notes |
|---|---|---|
| `JOBORA_ENV` | `development` | `production` enables fail-closed secret checks |
| `JWT_SECRET`, `CREDENTIAL_KEY` | auto (dev) | **required in prod**, vault them |
| `DATABASE_URL` | SQLite default | `postgresql+psycopg2://…` in prod (auto-normalized) |
| `REDIS_URL` | empty (in-memory) | shared rate-limit/cache/queue in prod |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | set to seed an admin | no default admin |
| `S3_BUCKET` + AWS creds | empty (local disk) | resumes + evidence in prod |
| `SMTP_*` | console fallback | real email in prod |
| `SENTRY_DSN`, `POSTHOG_API_KEY` | empty (off) | monitoring (gated) |
| `BETA_INVITE_REQUIRED` | `0` | `1` to gate signups by invite code |
| Provider keys | empty (gated) | `ADZUNA_*`, `JOOBLE_API_KEY`, `JSEARCH_API_KEY`, `WORKABLE_*`, `GREENHOUSE_BOARDS`, `LEVER_COMPANIES`, `ASHBY_BOARDS` |

### Database
- **Dev (SQLite):** tables are auto-created on startup (`create_all` +
  `ensure_sqlite_columns`); no migration step needed.
- **Production (Postgres):** schema is managed by **Alembic** — `alembic upgrade
  head` (the Docker entrypoint runs this automatically; current head
  `d4e5f6a7b8c9`).

### Run
```bash
# from backend/, with the venv active
ADMIN_EMAIL=you@example.com ADMIN_PASSWORD='ChangeMe!123' \
  uvicorn app.main:app --port 8000 --reload
```
Verify: `curl http://localhost:8000/api/health` → `{"status":"ok"}` and
`GET /api/ready` for subsystem status.

### Tests
```bash
python -m pytest -q          # 44 backend tests
```

## 2. Frontend
```bash
cd frontend
npm install
npm run dev                  # Vite dev server on http://localhost:5173
```
The Vite dev server **proxies `/api` → `http://localhost:8000`**, so run the backend
alongside it. For a production build: `npm run build` → static `dist/`.

### Frontend → API base
By default the app calls same-origin `/api` (dev proxy / same-host deploy). For a
split-host deploy, set `VITE_API_BASE_URL` at build time (e.g.
`https://api.jobora.app/api`) and add the SPA origin to the backend `CORS_ORIGINS`.

### End-to-end (Playwright) smoke suite
```bash
cd frontend
npm run test:e2e:install     # one-time: download Chromium
npm run test:e2e             # starts the Vite dev server; backend must be on :8000
```
Produces `PLAYWRIGHT_REPORT.md` + screenshots in `frontend/e2e/screenshots/`.
(Set `JOBORA_ADMIN_EMAIL` / `JOBORA_ADMIN_PASSWORD` if your admin differs from the
defaults in `e2e/support.js`.)

## 3. First-run checklist
1. Backend healthy (`/api/health`), `/api/ready` shows DB ok.
2. Log in as the seeded admin; change the password.
3. (If invites on) generate codes in **Admin → Operations → Invites**.
4. Register a user → approve in **Admin → User Management** → log in.
5. Upload a resume → **Find Jobs** returns results → **Track & Apply** → it appears
   in **Activity Log** as **Tracked**.

## Docker (optional)
A backend `Dockerfile` + `entrypoint.sh` (runs `alembic upgrade head` then uvicorn
on `$PORT`) and a `docker-compose.yml` are included. Build with
`--build-arg INSTALL_BROWSERS=0` to skip Chromium if you don't run live automation.
