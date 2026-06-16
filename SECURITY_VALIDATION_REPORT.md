# B0 Security Validation Report — CRITICAL findings closed

Scope: Phase B0. Goal: close all three CRITICAL findings from
`PRODUCTION_AUDIT.md`. No new features, no new platforms. All checks below were
executed against the code.

## Result: 3/3 CRITICAL findings CLOSED ✅

| Finding | Status | Evidence |
|---|---|---|
| **C1** Hardcoded secret fallbacks | ✅ Closed | secrets env-only; prod fail-closed; old defaults banned |
| **C2** Hardcoded admin credentials | ✅ Closed | no default admin; env-only; forced password change |
| **C3** No rate limiting | ✅ Closed | Redis-backed limits on login/register/apply/search |

---

## C1 — Remove hardcoded secrets / fail-closed config

| Check | Result |
|---|---|
| No secret used as a default in `config.py` (old values only in banned-list) | **PASS** |
| `JOBORA_ENV=production` + no `JWT_SECRET`/`CREDENTIAL_KEY` → refuses to start | **PASS** (`ConfigError`) |
| Prod rejects the old committed `CREDENTIAL_KEY` (banned) | **PASS** |
| Prod rejects a non-Fernet `CREDENTIAL_KEY` | **PASS** |
| Dev with no secrets → ephemeral keys generated + loud warning | **PASS** |
| Prod with valid secrets → boots | **PASS** |

Implementation: `app/config.py` (`_resolve_jwt_secret`, `_resolve_credential_key`,
`_BANNED_SECRETS`, `ConfigError`).

> ⚠️ **Action required:** the old `CREDENTIAL_KEY` was previously committed to git
> history. It is now blocked from use, but must be treated as **compromised** —
> rotate any data encrypted with it and consider scrubbing it from git history.

## C2 — Remove seeded admin credentials

| Check | Result |
|---|---|
| No `admin@jobapplier.com` / `Admin@123` in code | **PASS** |
| Old default admin login | **PASS** → 401 (account not seeded) |
| Admin seeded only when `ADMIN_EMAIL` + `ADMIN_PASSWORD` set | **PASS** |
| Seeded admin login (env creds) | **PASS** → `is_admin=True` |
| Forced password change flag | **PASS** → `must_change_password=True`, cleared on change (min len 8) |
| No env creds → no admin seeded (warning logged) | **PASS** |

Implementation: `app/main.py::seed_admin`, `User.must_change_password`,
`schemas.TokenOut.must_change_password`, `routers/profile.py`.

## C3 — Redis rate limiting

| Check | Result |
|---|---|
| Limiter module (Redis + in-memory fallback) | **PASS** (`app/ratelimit.py`, `cache.incr`) |
| Login limited per IP | **PASS** → with limit 5/min, attempts 6–7 returned **429** |
| Wired: login, register, apply (burst+daily), search | **PASS** (grep: 1/1/2/1) |
| 429 returns `Retry-After` | **PASS** |

Defaults (env-tunable): login 10/min, register 10/hr, apply 3/min + 30/day, search 30/min.

---

## Supporting verification
- **Migration chain** (3 revisions: initial → submission pipeline →
  must_change_password) applies cleanly on a fresh DB: **PASS**.
- **App boots** with env secrets + env admin; `/api/health` ok: **PASS**.
- Existing behavior intact (auth, evidence, submission gates unchanged).

## Deliverables
- `app/config.py` — env-only secrets, fail-closed validation, banned-list.
- `app/ratelimit.py` + `cache.incr` — rate limiting.
- `app/main.py` — env-only admin seeding.
- Migration `0ec9a06a5084_must_change_password`.
- `.env.example` (updated), `.env.production.example`, `SECURITY.md` (incl.
  migration + deployment instructions), this report.

## Out of scope (next: HIGH / Phase B1)
Background queue for apply (H1), JWT refresh + revocation (H2), S3 for
uploads/evidence (H3), index `applications.user_id` + unique constraint (H4),
signup password policy + email verification (H5). Tracked in `PRODUCTION_AUDIT.md`.
