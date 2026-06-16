# Jobara — Production Deployment Guide

Covers three paths: **Render** (easiest, blueprint included), **Railway**, and
**AWS** (ECS/Fargate or a single EC2 box). All three run the same artifacts:

- `backend/Dockerfile` — FastAPI; entrypoint runs `alembic upgrade head` then uvicorn.
- `frontend/Dockerfile` — Vite build → nginx (proxies `/api`), OR deploy `frontend/dist` as a static site.
- `docker-compose.yml` — full stack for a single VPS/EC2.

## Pre-deploy checklist (all platforms)

1. **Generate secrets:**
   ```bash
   python -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(48))"
   python -c "from cryptography.fernet import Fernet; print('CREDENTIAL_KEY=' + Fernet.generate_key().decode())"
   ```
2. Use **managed Postgres + Redis** (don't run them on the same box as the API for real traffic).
3. Set `CORS_ORIGINS` and `APP_BASE_URL` to your web app's public URL.
4. Set `SMTP_*` and `EXPOSE_RESET_TOKEN=0` so reset links are emailed, not returned.
5. The API is **stateless** — scale it horizontally; Redis is the shared cache.
6. Migrations apply automatically on deploy (entrypoint). To change schema later:
   `alembic revision --autogenerate -m "msg"`, commit, redeploy.

See `.env.production.example` for the full variable list.

---

## Option A — Render (recommended, blueprint included)

`render.yaml` provisions everything: Postgres, Redis, the API (Docker), and the
SPA (static).

1. Push the repo to GitHub.
2. Render Dashboard → **New → Blueprint** → select the repo. Render reads `render.yaml`.
3. It creates `jobara-db`, `jobara-redis`, `jobara-api`, `jobara-web`. `DATABASE_URL`,
   `REDIS_URL`, and `JWT_SECRET` are wired/generated automatically.
4. Fill the `sync: false` vars in the dashboard:
   - **jobara-api:** `CREDENTIAL_KEY` (Fernet key), `CORS_ORIGINS` = your web URL
     (e.g. `https://jobara-web.onrender.com`), `APP_BASE_URL` = same, plus `SMTP_*`.
   - **jobara-web:** `VITE_API_BASE_URL` = `https://jobara-api.onrender.com/api`.
5. Deploy. The API healthchecks `/api/health`; migrations run on boot.
6. Visit the `jobara-web` URL. Log in as `admin@jobapplier.com` / `Admin@123` and
   **change the admin password immediately** (or set `ADMIN_EMAIL`/`ADMIN_PASSWORD`).

> Free Postgres/Redis plans are fine to trial; move to paid plans for persistence
> guarantees and to avoid idle spin-down.

---

## Option B — Railway

Railway autodetects Dockerfiles and provisions Postgres/Redis as plugins.

1. **New Project → Deploy from GitHub repo.**
2. **Add Postgres** and **Add Redis** plugins (Railway injects `DATABASE_URL` /
   `REDIS_URL` reference variables). The app normalizes Railway's `postgres://`
   scheme automatically.
3. **API service:** set root/Dockerfile to `backend/Dockerfile` (context `backend/`).
   Variables:
   ```
   DATABASE_URL=${{Postgres.DATABASE_URL}}
   REDIS_URL=${{Redis.REDIS_URL}}
   JWT_SECRET=...           CREDENTIAL_KEY=...
   CORS_ORIGINS=https://<your-web-domain>
   APP_BASE_URL=https://<your-web-domain>
   EXPOSE_RESET_TOKEN=0
   SMTP_HOST=... SMTP_USER=... SMTP_PASSWORD=...
   ```
   Expose port 8000; healthcheck `/api/health`.
4. **Web service:** either
   - a second service from `frontend/Dockerfile` (nginx), set its public domain; or
   - deploy `frontend/dist` to any static host (Vercel/Netlify/Cloudflare Pages)
     with build env `VITE_API_BASE_URL=https://<api-domain>/api`.
5. Migrations run on deploy via the entrypoint. Generate a domain for the web service and log in.

---

## Option C — AWS

### C1. Single EC2 box (simplest — docker-compose)
Good for a first production box / staging.

```bash
# On an Ubuntu EC2 instance with Docker + compose installed:
git clone <your-repo> && cd jobara
cp .env.production.example .env     # fill in secrets + (optionally) keep bundled db/redis
docker compose up -d --build
```
- The bundled `db` (Postgres) and `redis` services run in the compose network.
  For production durability, point `DATABASE_URL`/`REDIS_URL` at **RDS** and
  **ElastiCache** instead and remove the `db`/`redis` services.
- Put **nginx or an ALB** in front of the `web` service (port 8080) and terminate
  TLS there (ACM cert / Let's Encrypt). `web` already reverse-proxies `/api` to `api`.
- Open only 80/443 to the world; keep 8000 internal.

### C2. ECS Fargate (scalable, managed)
1. **Build & push images** to ECR:
   ```bash
   aws ecr create-repository --repository-name jobara-api
   aws ecr create-repository --repository-name jobara-web
   docker build -t <acct>.dkr.ecr.<region>.amazonaws.com/jobara-api ./backend
   docker build -t <acct>.dkr.ecr.<region>.amazonaws.com/jobara-web \
     --build-arg VITE_API_BASE_URL=https://api.<your-domain>/api ./frontend
   docker push <acct>.dkr.ecr.<region>.amazonaws.com/jobara-api
   docker push <acct>.dkr.ecr.<region>.amazonaws.com/jobara-web
   ```
2. **RDS PostgreSQL** + **ElastiCache Redis** in the same VPC.
3. **Secrets Manager / SSM** for `JWT_SECRET`, `CREDENTIAL_KEY`, `DATABASE_URL`,
   `REDIS_URL`, `SMTP_*`; inject as task-definition secrets.
4. **ECS services:**
   - `jobara-api`: the API image, port 8000, ALB target group health check `/api/health`.
     Migrations run on task start (entrypoint). Set `desiredCount ≥ 2` for HA.
   - `jobara-web`: the nginx image, port 80, behind the same ALB on `/`.
5. **ALB** routes `/api/*` → api target group, `/*` → web target group; HTTPS via ACM.
6. Logs go to **CloudWatch** (the app emits structured JSON with `x-request-id`).

> Prefer keeping API and web behind one ALB (same origin) so you don't need CORS.
> If you split domains, set `CORS_ORIGINS` (API) and `VITE_API_BASE_URL` (web build).

---

## Post-deploy verification

```bash
curl https://<api-domain>/api/health     # {"status":"ok"}
curl https://<api-domain>/api/ready       # database.ok=true, cache.backend=redis, email.backend=smtp
```
- `cache.backend` should read **redis** (not memory) in production.
- `email.backend` should read **smtp**.
- Log in to the web app, confirm admin → approve a user → user can search jobs.

## Operational notes
- **Backups:** enable automated snapshots on managed Postgres.
- **Scaling:** add API replicas; Redis-backed cache keeps them consistent.
- **Rotating `CREDENTIAL_KEY`** invalidates stored portal credentials — rotate deliberately.
- **Uploads:** resumes are written to the `uploads` volume / container FS. For
  multi-replica or Fargate, mount shared storage (EFS) or move uploads to S3
  (next hardening step).
