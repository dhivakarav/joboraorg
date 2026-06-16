# Jobara — Complete Setup Guide

Production-shaped stack: **FastAPI** (API) · **PostgreSQL** (DB) · **Redis** (cache) ·
**React + Vite** (web, served by nginx in Docker) · **Docker Compose** (orchestration).

Everything has a **zero-config fallback** — the app runs locally with **SQLite +
in-memory cache + console email** and no API keys. Set env vars to switch to
Postgres / Redis / SMTP / Claude in production.

---

## 1. Prerequisites

| Tool | Version | For |
|---|---|---|
| Docker + Docker Compose | 24+ | Recommended path (everything containerised) |
| Python | 3.9+ (3.11 in Docker) | Manual backend |
| Node.js | 20+ | Manual frontend |
| Git | any | Clone |

You need **either** Docker **or** (Python + Node) — not both.

---

## 2. Quick Start — Docker (recommended)

Runs Postgres + Redis + API + Web together.

```bash
cd jobora

# 1. Create your env file from the template
cp .env.example .env

# 2. Fill in the two REQUIRED secrets in .env:
#    JWT_SECRET    — any long random string
#    CREDENTIAL_KEY — generate one:
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
#    paste the output as CREDENTIAL_KEY=...

# 3. Build and start the whole stack
docker compose up --build
```

Then open:
- **Web app:** http://localhost:8080
- **API:** http://localhost:8000  · docs at http://localhost:8000/docs
- **Readiness:** http://localhost:8000/api/ready

The API container runs `alembic upgrade head` automatically on boot (see
`backend/entrypoint.sh`), so the Postgres schema is created/migrated before the
server starts. Stop with `Ctrl+C`; tear down with `docker compose down`
(add `-v` to also wipe the Postgres/Redis/upload volumes).

---

## 3. Manual Local Dev (no Docker)

Runs on SQLite + in-memory cache + console email — no infra needed.

### 3a. Backend

```bash
cd jobora/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run it (creates jobora.db + seeds the admin account on first boot)
uvicorn app.main:app --reload --port 8000
```

API on http://localhost:8000. On SQLite the app calls `create_all` at startup,
so you don't need to run migrations for local dev.

### 3b. Frontend

```bash
cd jobora/frontend
npm install
npm run dev          # http://localhost:5173 (proxies /api → :8000)
```

Open http://localhost:5173.

---

## 4. Environment Variables

Set in `.env` (Docker) or your shell (manual). **Only the two security keys are
required**; everything else has a working default.

### Required for production
| Variable | Description |
|---|---|
| `JWT_SECRET` | Secret used to sign JWTs. Use a long random string. |
| `CREDENTIAL_KEY` | Fernet key encrypting stored portal credentials. Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

### Database & cache
| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///<backend>/jobora.db` | Use `postgresql+psycopg2://user:pass@host:5432/db` in prod. |
| `REDIS_URL` | _(unset → in-memory)_ | e.g. `redis://localhost:6379/0`. Shared cache for horizontal scaling. |

### Postgres (Docker compose only — wires `DATABASE_URL` for you)
| Variable | Default |
|---|---|
| `POSTGRES_USER` | `jobara` |
| `POSTGRES_PASSWORD` | `jobara` (change it) |
| `POSTGRES_DB` | `jobara` |

### Email (optional — console fallback if unset)
| Variable | Default | Description |
|---|---|---|
| `SMTP_HOST` | _(unset → console)_ | SMTP server host |
| `SMTP_PORT` | `587` | |
| `SMTP_USER` / `SMTP_PASSWORD` | _(empty)_ | SMTP auth |
| `SMTP_FROM` | `Jobara <no-reply@jobara.app>` | From header |
| `SMTP_TLS` | `1` | STARTTLS on/off |
| `APP_BASE_URL` | `http://localhost:5173` | Links in emails |

### Job providers (optional — expands India/Dubai/Singapore coverage)
| Variable | Description |
|---|---|
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | Free key from developer.adzuna.com (India, Singapore) |
| `JOOBLE_API_KEY` | Free key from jooble.org/api/about (incl. UAE/Dubai) |
| `GREENHOUSE_BOARDS` | Comma-separated company board tokens (e.g. `stripe,airbnb`) |
| `LEVER_COMPANIES` | Comma-separated Lever company slugs |

### Aggregator tuning
| Variable | Default | Description |
|---|---|---|
| `JOB_CACHE_TTL` | `900` | Cached search lifetime (seconds) |
| `PROVIDER_TIMEOUT` | `15` | Per-provider HTTP timeout (seconds) |
| `PROVIDER_MIN_INTERVAL` | `1.0` | Min seconds between calls to one provider |

### Auth / reset
| Variable | Default | Description |
|---|---|---|
| `RESET_TOKEN_TTL_MINUTES` | `30` | Password-reset token lifetime |
| `EXPOSE_RESET_TOKEN` | `1` | Return reset link in API response (dev). Set `0` once SMTP is live. |

### Logging
| Variable | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Root log level (structured JSON logs) |

### AI (Phase 3 — optional; heuristics used when unset)
| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | _(unset)_ | Enables Claude-powered features |
| `AI_MODEL` | `claude-opus-4-8` | Model ID |

### Live apply automation (opt-in)
| Variable | Default | Description |
|---|---|---|
| `JOBORA_LIVE` | `0` | `1` enables real Playwright form submission (needs `playwright install chromium`) |

---

## 5. Database Setup

### Local dev (SQLite) — automatic
Nothing to do. On first boot the app creates `backend/jobora.db` with all tables
and seeds the admin account.

### Production (PostgreSQL) — Alembic migrations
The schema is managed by Alembic (`backend/alembic/`).

```bash
cd backend
export DATABASE_URL="postgresql+psycopg2://user:pass@host:5432/jobara"

alembic upgrade head      # apply all migrations (create/upgrade schema)
alembic current           # show the applied revision
alembic history           # list migrations
```

In Docker this runs automatically via `entrypoint.sh`. After changing models,
generate a new migration:

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

### Default admin account (seeded automatically)
- **Email:** `admin@jobapplier.com`
- **Password:** `Admin@123`

Change these via env in production (or update `ADMIN_EMAIL`/`ADMIN_PASSWORD`
in `app/config.py`). New users register → land in "pending" → an admin
approves them before they can log in.

---

## 6. Run Commands

| Goal | Command |
|---|---|
| Full stack (Docker) | `docker compose up --build` |
| Stop stack | `docker compose down` (`-v` also wipes volumes) |
| Backend only (dev) | `cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000` |
| Backend (prod-style) | `cd backend && ./entrypoint.sh` |
| Frontend dev server | `cd frontend && npm run dev` |
| Frontend prod build | `cd frontend && npm run build` (output in `dist/`) |
| Frontend preview build | `cd frontend && npm run preview` |
| Apply DB migrations | `cd backend && alembic upgrade head` |
| Enable live auto-submit | `cd backend && playwright install chromium && JOBORA_LIVE=1 uvicorn app.main:app --port 8000` |

---

## 7. Testing Commands

### Health & readiness
```bash
curl http://localhost:8000/api/health      # {"status":"ok"}
curl http://localhost:8000/api/ready        # reports db/cache/email/ai status
```

### End-to-end flow test
A full E2E harness exercises every endpoint (auth → resume → jobs → apply →
admin → reset). With the API running:

```bash
cd backend
.venv/bin/python /tmp/e2e.py     # if you saved the harness, else see below
```

Quick manual smoke test:
```bash
# register → admin approve → login → search real jobs
curl -s -X POST localhost:8000/api/auth/register -H 'Content-Type: application/json' \
  -d '{"full_name":"Test","email":"test@x.com","password":"pass123","job_title":"engineer"}'

ADMIN=$(curl -s -X POST localhost:8000/api/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"admin@jobapplier.com","password":"Admin@123"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

UID=$(curl -s localhost:8000/api/admin/users -H "Authorization: Bearer $ADMIN" \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)[0]["id"])')
curl -s -X POST localhost:8000/api/admin/users/$UID/approve -H "Authorization: Bearer $ADMIN"

TOK=$(curl -s -X POST localhost:8000/api/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"test@x.com","password":"pass123"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -s "localhost:8000/api/jobs?q=engineer&limit=5" -H "Authorization: Bearer $TOK"
```

### Frontend build check
```bash
cd frontend && npm run build      # fails on any compile/import error
```

### Verify migrations on a throwaway DB
```bash
cd backend
DATABASE_URL="sqlite:////tmp/check.db" .venv/bin/alembic upgrade head
```

---

## 8. Production Deployment Notes

- **DB / cache:** point `DATABASE_URL` at managed Postgres (RDS / Neon / Supabase)
  and `REDIS_URL` at managed Redis (Upstash / ElastiCache).
- **Secrets:** set `JWT_SECRET` and `CREDENTIAL_KEY` from a secrets manager.
  Rotating `CREDENTIAL_KEY` invalidates stored portal credentials.
- **Email:** set `SMTP_*` and `EXPOSE_RESET_TOKEN=0`.
- **Migrations:** run in the deploy pipeline / entrypoint (`alembic upgrade head`).
- **Scaling:** the API is stateless — run multiple replicas behind a load
  balancer; Redis provides the shared job cache. Probe `/api/ready`.
- **Logs:** structured JSON on stdout with per-request IDs (`x-request-id`).

---

## 9. Troubleshooting

| Symptom | Fix |
|---|---|
| `Fernet key must be 32 url-safe base64-encoded bytes` | `CREDENTIAL_KEY` is invalid — regenerate with the Fernet command above. |
| Login returns 403 "pending admin approval" | Expected — an admin must approve the user first. |
| Job search returns 0 | Query matches job *titles*; try a broader role, or set `ADZUNA_*`/`JOOBLE_*` keys for more sources. |
| Cache shows `memory` in `/api/ready` | `REDIS_URL` unset — fine for dev; set it for production. |
| Resume upload "Internal Server Error" | Ensure it's a PDF ≤ 5 MB. |
| Docker API can't reach DB | `db` healthcheck must pass first; compose waits via `depends_on: condition: service_healthy`. |
