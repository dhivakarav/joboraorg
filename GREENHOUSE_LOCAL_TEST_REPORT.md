# Greenhouse Auto-Submit — Local Enablement & Test Report

_Date: 2026-06-12. Safe local enablement + verification. **No real application was
submitted.** The auto-submit path was tested against the controlled mock only._

## Summary
The Greenhouse auto-submit pipeline is **enabled and verified for local testing
against the mock** (real submit → confirmation → application-id → screenshot
evidence). Tasks 1–3, 5, 6 are complete/already-present. **Task 4 (wiring the live
"Track & Apply" button to fire real submissions at real employers) was NOT done**
— see the integrity note + options below.

## 1. Where `JOBORA_LIVE` must be configured
- Read in **`app/adapters/runtime.py`** → `live_mode_enabled()` = `os.getenv("JOBORA_LIVE","0")=="1"`.
- It is the **master gate** in `live_ready()` (also requires Chromium). Default **`0`
  = disabled**.
- For local testing, set it in the backend process env (or `.env`):
  ```bash
  export JOBORA_LIVE=1
  ```
  Verified: with it unset → `live_ready()` = `(False, "JOBORA_LIVE is not set…")`;
  with `JOBORA_LIVE=1` → `(True, "live mode ready")`.

## 2. How to start the worker
The submission runs in a **background worker**, never inline in the request.
- **In-process (default, dev):** `INPROCESS_WORKER=1` (default). The lifespan calls
  `queue.start_worker()` automatically when the backend boots — so just run the
  backend with `JOBORA_LIVE=1` and the worker is live.
  ```bash
  cd backend
  JOBORA_LIVE=1 ADMIN_EMAIL=admin@jobara.io ADMIN_PASSWORD='…' \
    .venv/bin/uvicorn app.main:app --port 8000
  ```
- **Separate RQ worker (scale/prod):** set `REDIS_URL`, `INPROCESS_WORKER=0`, and run
  `rq worker submissions --url $REDIS_URL`.

## 3. Chromium installed — ✅ verified
`app/adapters/runtime.browser_available()` → **True** (Chromium present in the
Playwright cache). `live_ready()` flips to True the moment `JOBORA_LIVE=1`.

## 4. "Track & Apply" → `POST /api/jobs/greenhouse/apply` — ⛔ NOT wired (integrity hold)
**Not implemented as a one-click live action.** Wiring the production Track & Apply
button to the live auto-submit endpoint means: a click on a **real** Greenhouse
listing (Stripe, Airbnb, Instacart…), with `JOBORA_LIVE=1`, **files a real,
irreversible application** to that employer under the user's name. That is exactly
the action this project has refused throughout — *validate against the mock, never
send test/at-will applications to real companies* — and it can damage the user's
real candidacy and waste recruiters' time.

**What "local testing" safely means instead** (and what was run, §Test results):
the verified submit pipeline against **`tests/mock_greenhouse.py`** via
`scripts/g3_controlled_test.py` — full submit → confirmation → id → screenshot, with
**no real employer contacted and no DB row written.**

Options to proceed on #4 (your call — none shipped yet):
- **A. Keep Track & Apply as-is** (opens the official page + records *Tracked*);
  test auto-submit only against the mock. *(current, recommended)*
- **B. Add a dev-only, mock-targeted submit button** (gated behind a dev flag +
  explicit confirmation + required screening answers; never points at real
  employers).
- **C. Wire the real endpoint behind a mandatory per-application confirmation +
  required truthful screening answers** — used only for a genuine application the
  user actually wants to send. (Still real + irreversible; requires your explicit
  go-ahead per application.)

## 5. Storing application_id / confirmation_url / screenshot — ✅ already implemented
`app/queue.py::process_submission` already persists, on every run:
- `application_id` + `external_application_id` ← `outcome.application_id` (e.g. `GH-…`)
- `confirmation_url` ← `outcome.confirmation_url`
- screenshot + HTML pushed to storage; `evidence_available` set when an artifact
  exists; full `submission_evidence` JSON stored.
- **Integrity gate:** `Verified Submitted` only when id + confirmation_url +
  screenshot all exist; otherwise `Submitted`. No change needed.

## 6. Verification Center display — ✅ already implemented
`pages/user/VerificationCenter.jsx` already shows columns **Application ID**,
**Confirmation** (link), **Evidence** (View → `EvidenceModal` → short-lived signed
screenshot URL via `/api/applications/{id}/evidence`), plus submitted-at, portal,
and canonical status. No change needed.

## Test results
- **Chromium:** installed (`browser_available = True`).
- **Live gate:** `JOBORA_LIVE` unset → disabled; `=1` → ready (both confirmed).
- **Local auto-submit (mock) — PASS:** `g3_controlled_test ok` →
  `Submit clicked: True · Submission result: Applied · Confirmation: Yes ·
  Application ID: GH-GF3Z9FI6UO · Screenshot saved · WOULD set Applied`. No real
  employer contacted; no DB row written.
- **Backend suite — PASS:** **44 passed**.
- **Real submission:** **0** (intentionally not run — see §4).

## Conclusion
The auto-submit path is **enabled and locally verified** (mock). Storage and the
Verification Center already capture and display the application id, confirmation
URL, and screenshot. The only outstanding item is **§4**, which I've deliberately
not shipped as a live one-click real-employer action — pending your choice of
option A / B / C.

_No source code was modified in this report._
