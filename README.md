# Jobora — Real Job Discovery & Application Platform

Jobora aggregates **genuine, currently-open jobs** from official company sources,
lets users discover and one-click **apply through the real application page**, and
**tracks every application** — across the India, Dubai, Singapore, and remote
markets. No mock data.

Glossy black-and-white UI · JWT auth with admin approval · live job aggregation.

## How "applying" works (important)

Jobora is a **discovery + assisted-apply** platform, not a credential bot:

- It pulls real openings from **official provider APIs** (Greenhouse, Lever,
  Remotive, Arbeitnow; plus Adzuna/Jooble when keys are set).
- Every job carries a real `apply_url` and a **Verified** badge once its source
  is validated.
- Clicking **Apply** opens the genuine application page and records the
  application in the user's tracker.
- **Auto-Discover** fetches all real jobs matching the user's filters and saves
  them for review.

> Truly unattended auto-submission into LinkedIn/Naukri/Indeed using a user's
> stored password violates those sites' Terms of Service and anti-bot systems, so
> it is **not** part of the default product. The Playwright modules under
> `automation/portals/` remain as opt-in scaffolding (`JOBORA_LIVE=1`) for
> environments where you are explicitly authorised to automate a given account.

---

## Tech stack

| Layer        | Tech                                            |
| ------------ | ----------------------------------------------- |
| Frontend     | React + Vite + TailwindCSS                      |
| Backend      | Python + FastAPI                                |
| Database     | SQLite + SQLAlchemy ORM                         |
| Auth         | JWT (email/password), bcrypt hashing            |
| Job sources  | httpx async aggregator over official job APIs   |
| Automation   | Playwright (async) — opt-in scaffolding only    |
| Resume parse | pdfplumber                                      |
| Cred storage | Fernet-encrypted portal credentials             |

## Job sources

| Provider   | Key needed | Coverage                                   |
| ---------- | ---------- | ------------------------------------------ |
| Greenhouse | no         | Real openings from curated real companies  |
| Lever      | no         | Real openings from curated real companies  |
| Remotive   | no         | Remote jobs                                |
| Arbeitnow  | no         | EU + remote jobs                           |
| Adzuna     | yes (free) | India (`in`), Singapore (`sg`), + more     |
| Jooble     | yes (free) | Global incl. Dubai/UAE (free-text location)|

Add company boards via `GREENHOUSE_BOARDS` / `LEVER_COMPANIES` (comma-separated).
Enable Adzuna/Jooble by setting their API keys — see Configuration.

---

## Project layout

```
jobora/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app + admin seeding
│   │   ├── config.py          # settings, keys, portal list
│   │   ├── database.py        # engine + session
│   │   ├── models.py          # SQLAlchemy models (5 tables)
│   │   ├── schemas.py         # Pydantic schemas
│   │   ├── security.py        # bcrypt, JWT, Fernet encryption
│   │   ├── deps.py            # auth dependencies
│   │   ├── routers/           # auth, resume, profile, portals,
│   │   │                      #   filters, applications, apply,
│   │   │                      #   dashboard, admin
│   │   ├── utils/resume_parser.py
│   │   └── automation/
│   │       ├── engine.py      # orchestration, SSE events, dedupe, limits
│   │       └── portals/       # linkedin, naukri, indeed, foundit,
│   │                          #   bayt, jobstreet (+ base)
│   ├── requirements.txt
│   └── uploads/               # stored resumes
└── frontend/
    └── src/
        ├── api/client.js
        ├── context/AuthContext.jsx
        ├── components/        # Layout, UI primitives
        └── pages/             # auth + user/ + admin/
```

---

## Running locally

### 1. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The SQLite DB and the hardcoded admin account are created automatically on
first boot. API docs at http://localhost:8000/docs.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxies /api → :8000)
```

---

## Accounts

- **Admin:** `<ADMIN_EMAIL>` / `<ADMIN_PASSWORD>` → redirected to `/admin`.
- **New users** register at `/register`, land on a *pending approval* screen,
  and cannot log in until the admin approves them in **User Management**.

---

## How auto-apply works

`POST /api/apply/start` launches a background task (one per user) that:

1. Loads the user's active portals, filters, and parsed resume.
2. For each portal, logs in and searches using the role/keyword + location filters.
3. Fills and submits applications, logging every result to the DB.
4. Enforces the **daily limit**, **skips duplicate jobs** (by job-URL hash),
   and streams live progress over **Server-Sent Events** at
   `GET /api/apply/stream?token=<jwt>`.

`POST /api/apply/stop` cancels the running task.

### Simulation vs. live mode

By default Jobora runs in **simulation mode** so the entire app is runnable
without real portal credentials or installed browsers — the engine produces
realistic synthetic application results.

To drive **real browsers**:

```bash
playwright install chromium
JOBORA_LIVE=1 uvicorn app.main:app --port 8000
```

Each portal module in `app/automation/portals/` contains the real Playwright
login/search/apply selectors used in live mode. Selectors on real job sites
change often and many portals actively block automation — treat the live
drivers as a starting point and use responsibly within each site's terms.

---

## API reference

**Auth:** `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`

**User:** `POST /api/resume/upload`, `GET/PUT /api/resume/parsed`,
`PUT /api/profile/update`, `PUT /api/profile/password`,
`GET/POST /api/portals`, `PATCH /api/portals/{name}/toggle`,
`GET/POST /api/filters`, `GET /api/applications`,
`POST /api/apply/start`, `POST /api/apply/stop`, `GET /api/apply/stream`,
`GET /api/dashboard/stats`

**Admin** (require `is_admin`): `GET /api/admin/stats`, `GET /api/admin/users`,
`POST /api/admin/users/{id}/approve`, `POST /api/admin/users/{id}/suspend`,
`GET /api/admin/users/{id}/details`, `GET /api/admin/applications`

---

## Configuration

Override via environment variables (see `app/config.py`):

- `JWT_SECRET` — JWT signing secret (set in production).
- `CREDENTIAL_KEY` — Fernet key for portal-credential encryption.
  Generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
- `DATABASE_URL` — defaults to local SQLite.
- **Job providers:** `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `JOOBLE_API_KEY`,
  `GREENHOUSE_BOARDS`, `LEVER_COMPANIES`.
- **Aggregator tuning:** `JOB_CACHE_TTL` (default 900s), `PROVIDER_TIMEOUT`
  (15s), `PROVIDER_MIN_INTERVAL` (per-provider rate limit, 1.0s).
- `JOBORA_LIVE` — `1` to enable the opt-in Playwright portal scaffolding.

### Production notes

- **Error handling:** each provider call is isolated + timed out; one failing
  source never breaks a search.
- **Rate limiting:** `PROVIDER_MIN_INTERVAL` throttles upstream calls; results
  are TTL-cached (`JOB_CACHE_TTL`) to minimise API usage.
- **Compliance:** only official documented APIs are used. `app/jobs/robots.py`
  provides a robots.txt gate for safely adding any future HTML-scraping source.
- **Secrets:** set `JWT_SECRET` and `CREDENTIAL_KEY` from the environment; never
  commit real keys.
