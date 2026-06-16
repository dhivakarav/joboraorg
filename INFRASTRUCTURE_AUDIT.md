# Infrastructure Audit

_Validated against the running app + real providers. No Greenhouse/Lever/Ashby/
matching/integrity logic was modified._

## Results
| # | Subsystem | Result | Evidence |
|---|---|---|---|
| 1 | **Greenhouse discovery** | ✅ PASS | Real public API fetched **2,267** jobs (`software engineer`) |
| 2 | **Lever Assisted Apply** | ✅ PASS | `manual_only=True`; `/api/jobs/assisted/prepare` + `/record` live; G0–G3 verified earlier |
| 3 | **Ashby Assisted Apply** | ✅ PASS | `manual_only=True`; same assisted endpoints; SPA DOM-state confirmation verified |
| 4 | **Resume upload + read-back** | ⚠️ PASS w/ caveat | Row persists; **encrypted-at-rest**; now **degrades gracefully** if undecryptable |
| 5 | **Activity tracking** | ✅ PASS | Canonical statuses only (`Tracked`/`Manual Apply`/…); **0 "Applied" leaks** |
| 6 | **Evidence storage** | ✅ PASS | save+read roundtrip OK (local backend; S3/R2 in prod) |
| — | **Health / Ready** | ✅ PASS | `/api/health` ok; `/api/ready` reports DB ok, cache, email, AI, live_apply |

## Finding & fix (resume encryption resilience)
- **Observed:** in **dev**, `CREDENTIAL_KEY` is unset → an **ephemeral** key is
  generated on each restart. A resume encrypted under a prior key then fails to
  decrypt (`InvalidToken`). Previously this **crashed every request** that loaded
  the profile (search, prepare, dashboard) with a 500.
- **Fixed:** `materialize_resume()` now catches decrypt failures, logs a warning,
  and returns "no usable resume" — search/dashboard stay up and the user is
  prompted to re-upload. (Error-handling hardening; no integrity/matching change.)
- **Production note:** prod **requires** a stable `CREDENTIAL_KEY` (the app refuses
  to start without it), so this only bites if the key is rotated/lost. Losing
  `CREDENTIAL_KEY` makes encrypted PII unrecoverable → store it in a secrets vault
  and **never rotate without a re-encryption migration.**

## Production prerequisites (must be set before real users)
- `JOBORA_ENV=production`, `JWT_SECRET`, `CREDENTIAL_KEY` (stable, vaulted).
- Managed **Postgres** (`DATABASE_URL`) — dev is SQLite, **not** production-safe.
- Managed **Redis** (`REDIS_URL`) — dev falls back to in-memory cache/limits
  (`cache.backend = memory`), which does **not** share state across replicas.
- **S3/R2** (`S3_BUCKET` + creds) — dev uses local disk, ephemeral on Railway.
- Run the **submission worker** (RQ) as a separate process under load.

## Verdict
All six subsystems function on real data. The only material gap is **environment
provisioning** (Postgres/Redis/S3 + stable secrets) — code is ready; infra must be
stood up per `DEPLOYMENT_GUIDE.md`.
