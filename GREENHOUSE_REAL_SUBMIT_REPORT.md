# Greenhouse Real-Submit — Implementation Report

_Date: 2026-06-12. Implements the chosen option: wire the real Greenhouse submit
behind a **mandatory per-application confirmation + required truthful answers**.
**No real application was filed** during implementation/testing (the live pipeline
was validated against the mock; `JOBORA_LIVE` left unset)._

## What was built
### Backend — one new READ-ONLY endpoint (no submit, no browser, no DB write)
`POST /api/jobs/greenhouse/form` (`app/routers/jobs.py`):
- Resolves `(board, job_id)` from the job, calls the public **Greenhouse Board API**
  (`fetch_fields`, httpx — fast, no Playwright), and returns the posting's
  **required + optional screening questions** (name, label, type, select options)
  plus the **profile prefill** (name/email/phone/resume filename) and a
  `profile_complete` flag. Core identity/resume/cover-letter fields are excluded
  from the question list.
- The existing **`POST /api/jobs/greenhouse/apply` is unchanged** — same hard gates
  (auth · rate limit · `approved=true` · Greenhouse source · resolvable form ·
  complete profile + real resume), still enqueues to the background worker, which
  only submits when `live_ready()` (i.e. `JOBORA_LIVE=1` + Chromium).

### Frontend — `GreenhouseSubmitWizard.jsx`
Opens when a **Greenhouse** job's apply button is clicked (`FindJobs` routes
Greenhouse → this wizard; Lever/Ashby → Assisted; others → Track & Apply):
1. Loads the required questions via `/greenhouse/form`.
2. Shows an **unmissable warning** ("This files a real application to {company} …
   cannot be undone"), the **identity/resume Jobora will submit**, and the
   **required screening questions** (text/textarea/select) for truthful answers.
3. A **mandatory confirmation checkbox** ("I confirm these answers are truthful and
   I want to submit a real application to {company}").
4. **"Submit real application"** is disabled until: profile complete **and** every
   required question answered **and** the checkbox ticked → then `POST
   /greenhouse/apply` with `answers` + `approved:true` → "Application queued" →
   directs the user to the **Verification Center** for the outcome + evidence.
5. A secondary **"Open & track instead"** keeps the safe non-submitting path.

### Tasks 5 & 6 — already implemented (verified, no change)
- **Store app id / confirmation URL / screenshot:** `queue.py::process_submission`
  already persists `application_id`, `confirmation_url`, `evidence_available`, and
  the screenshot/HTML evidence, with the integrity gate (Verified Submitted needs
  all three).
- **Verification Center display:** already shows **Application ID**, **Confirmation**
  (link), and **Evidence** (View → short-lived signed screenshot).

## Local enablement (recap)
- `JOBORA_LIVE=1` (gate in `app/adapters/runtime.py`); worker is in-process by
  default (`INPROCESS_WORKER=1`, auto-started in lifespan); Chromium installed
  (`browser_available=True`). With `JOBORA_LIVE` **unset**, a confirmed submit
  queues but the worker records **Manual Apply Required** (no real submission) —
  used during this work so nothing was sent.

## Tests & results
- **New backend tests** (`tests/test_greenhouse_submit.py`, 4):
  - `/greenhouse/form` returns the **required** questions (core/resume excluded;
    select options included);
  - `/greenhouse/apply` **requires approval** (400 without `approved`);
  - **rejects non-Greenhouse** source (400);
  - valid + resume + approved → **`Queued`** (enqueue stubbed; no browser).
- **Full backend suite: 48 passed** (44 → 48).
- **Frontend build: clean.**
- **Playwright E2E: 13/13 passed**, **0 console errors · 0 failed API requests · 0
  uncaught exceptions**. Test 11 updated for the wizard (verifies it opens; falls
  back to direct-track for non-Greenhouse). In this run no Greenhouse internship
  card was present (student internships-only filter) so it took the safe skip path.
- **Mock pipeline (earlier):** real submit → confirmation → `GH-…` id → screenshot,
  no real employer.
- **Real submissions filed: 0.**

## Safety posture
A real application is sent **only** when all of these hold: `JOBORA_LIVE=1`, the
worker is running, and the user completes the wizard with truthful answers **and**
the explicit confirmation. Choosing *which* real job to submit — and clicking the
final confirm — remains a deliberate, per-application human action. The
integrity model is intact: nothing is marked Verified Submitted without
confirmation + application id + screenshot.

## Files changed
- `backend/app/routers/jobs.py` — `+ /greenhouse/form` (read-only); imports.
- `frontend/src/components/GreenhouseSubmitWizard.jsx` — new.
- `frontend/src/pages/user/FindJobs.jsx` — route Greenhouse → wizard.
- `backend/tests/test_greenhouse_submit.py` — new tests.
- `frontend/e2e/smoke.spec.js` — test 11 updated for the wizard.
