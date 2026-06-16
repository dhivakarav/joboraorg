# Rollback Plan — Jobora

Goal: restore a known-good state fast, without data loss or integrity regressions.

## Decision guide
| Symptom | Action |
|---|---|
| Bad app behavior, schema unchanged | **App rollback** (§1) |
| Boot/healthcheck failing after deploy | App rollback (§1); inspect logs |
| Bad/partial migration | **Migration rollback** (§2) — only if safe |
| Data corruption / accidental deletion | **Restore from backup** (§3) |
| Bad config/secret | **Revert env var** (§4) — no redeploy of code |

## 1. App rollback (fastest, default)
- **Railway → API service → Deployments → pick the last healthy deploy → Redeploy
  / Rollback.** Railway keeps prior build images.
- CLI: `railway redeploy <deploymentId>` (or roll back via the dashboard).
- Then re-point the worker to the same release if it was changed.
- ✅ Use this first when the schema did **not** change in the bad release.

## 2. Migration rollback (only when a migration is the problem)
- Identify current head: `railway run alembic current`.
- Step down one revision: `railway run alembic downgrade -1`
  (or to a specific rev: `railway run alembic downgrade <revision>`).
- **Safety:** our recent migrations are **additive + non-destructive**
  (`a1b2c3d4e5f6` adds columns + relabels data; `b2c3d4e5f6a7` adds plan columns;
  `c3d4e5f6a7b8` adds `beta_invites`/`feedback` tables). Their `downgrade()` only
  drops the **added** columns/tables — existing user data is preserved.
- ⚠️ Never downgrade past a revision whose `downgrade` would drop a column that now
  holds real data you need. If unsure, prefer §3 (restore) over a destructive down.
- After downgrade, deploy the matching previous app image (§1) so code ↔ schema agree.

## 3. Restore from backup (data loss / corruption)
- **Postgres:** Railway managed backups → restore the most recent good snapshot
  to a new DB, verify, then repoint `DATABASE_URL`. Or from a `pg_dump`:
  `gunzip -c backup-YYYY-MM-DD.sql.gz | psql "$DATABASE_URL"`.
- **Object storage:** restore evidence/resume objects from bucket versioning
  (S3) or R2 lifecycle/backup. Evidence is append-only, so loss is rare.
- After restore, run §8 smoke test from `DEPLOY_CHECKLIST.md`.

## 4. Config/secret revert
- Revert the changed env var in Railway → service restarts.
- **Never rotate `CREDENTIAL_KEY`** as a "fix" — it makes existing encrypted
  resumes/credentials unreadable. If it was changed by mistake, restore the
  previous key from the vault. (The app degrades gracefully on undecryptable
  blobs, but the data is only recoverable with the original key.)

## 5. Integrity guarantees during rollback (must hold)
- No rollback path may surface "Applied" without evidence or fabricate data — the
  `display_status` gate is enforced in code at every release in the chain.
- If a rollback lands on a release **before** the integrity migration
  (`a1b2c3d4e5f6`), legacy rows could show stale `status` — re-run
  `scripts/fix_integrity_status.py` (or upgrade forward) before reopening signups.

## 6. Comms
- Flip `BETA_INVITE_REQUIRED=1` and stop issuing new invites during an incident.
- Post status to the beta channel; ask testers to pause.
- Log the incident: trigger, action taken, restore point, root cause, follow-up.

## Rollback SLA targets (beta)
- App rollback: **< 5 min**. Migration downgrade: **< 15 min**.
- DB restore: **< 60 min** (depends on snapshot size).
