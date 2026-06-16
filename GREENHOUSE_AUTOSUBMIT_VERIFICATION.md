# Greenhouse Auto-Submit — Verification Report

_Date: 2026-06-12. Read-only audit; no code modified, no application submitted._

> ⚠️ The auto-submit path, when fully enabled, **drives the real Greenhouse form
> and clicks Submit** (`greenhouse_production.apply` → `#submit_app`). Running it
> against a real posting files a **real, irreversible application** under the
> user's name. This report documents the implementation and a procedure — it does
> **not** execute it.

## 1. Where the auto-submit code lives
| Layer | File / symbol |
|---|---|
| **HTTP entry** | `app/routers/jobs.py` → `POST /api/jobs/greenhouse/apply` (`greenhouse_apply`) |
| **Queue / worker** | `app/queue.py` → `enqueue_submission` → `process_submission` (background; in-process or RQ) |
| **Runtime gates** | `app/adapters/runtime.py` → `live_ready`, `browser_available`, `live_mode_enabled` |
| **Submit pipeline** | `app/adapters/greenhouse_production.py` → `apply()` (real fill→submit→confirm→evidence), `resolve_form_url`, `parse_board_job` |
| **Field spec (read-only)** | `app/adapters/greenhouse_inspect.py` (G0–G1) |
| **Fill helpers** | `app/adapters/greenhouse_fill.py` → `fetch_fields` (G2) |
| **Confirmation/ID logic** | `app/adapters/greenhouse_submit.py` → `classify_confirmation`, `REF_PATTERNS` (`GH-…`), success/failure markers |
| **Adapter capability** | `app/adapters/greenhouse.py` (`auto_submit=True`), `app/adapters/base.py` (`LIVE_MODE`) |
| **Profile gate** | `app/services.py` → `profile_complete` |
| **Safe test harness** | `tests/mock_greenhouse.py`, `scripts/g3_controlled_test.py`, `scripts/inspect_greenhouse.py` |

> **UI wiring:** **No frontend button calls `/jobs/greenhouse/apply`.** The
> Greenhouse "Track & Apply" UI calls `/jobs/apply` (records *Tracked*). The
> auto-submit endpoint is reachable **only via a direct authenticated API call.**

## 2. Every gate that currently prevents execution
**At the endpoint (`/jobs/greenhouse/apply`):**
1. **Auth** — `get_approved_user` (must be logged-in + admin-approved).
2. **Rate limits** — `gh_apply_burst` (`RL_APPLY_BURST_PER_MIN`/min) + `gh_apply_day`
   (`RL_APPLY_PER_DAY`/day).
3. **Explicit approval** — `data.approved` must be `True`, else 400.
4. **Greenhouse only** — `data.source == "greenhouse"`, else 400.
5. **Form URL resolvable** — `resolve_form_url(job)` must return a URL, else 400.
6. **Complete profile + real resume** — `profile_complete` requires `name`, `email`,
   `phone`, and a **decryptable resume file on disk**, else 400.
   → on success: row created, `submission_status = "Queued"`, **enqueued** (never
   submitted inline).

**In the worker (`process_submission`):**
7. Row must still be `Queued`/`Processing`.
8. **`live_ready()`** (the master gate):
   - **`JOBORA_LIVE=1`** must be set (else → `Manual Apply Required`, no submit).
   - **Chromium installed** on disk (else → `Manual Apply Required`).

**In the pipeline (`greenhouse_production.apply`):**
9. Must **reach the form** (timeout → fail).
10. **Captcha/validation** detected after submit → `CAPTCHA Required` / `Failed` —
    **never** a false success.
11. **`Verified Submitted`** only if **confirmation + application id + stored
    screenshot** all exist; otherwise `Submitted`.

**Current live state (this machine):** `JOBORA_LIVE` **unset → disabled**;
`browser_available = True`; so `live_ready()` is **False** until `JOBORA_LIVE=1`.

## 3. Required environment variables
| Var | Needed for auto-submit | Notes |
|---|---|---|
| **`JOBORA_LIVE=1`** | ✅ **Required** | Master switch; default `0` = disabled |
| Playwright Chromium installed | ✅ Required | `playwright install chromium` (checked via `PLAYWRIGHT_BROWSERS_PATH` or default cache) |
| `RL_APPLY_BURST_PER_MIN`, `RL_APPLY_PER_DAY` | tuning | per-user burst/day caps |
| `INPROCESS_WORKER=1` (or a running RQ worker) | ✅ | the submit runs in the worker |
| `UPLOAD_DIR` / storage | ✅ | evidence (screenshot/HTML) is written here |
| Standard app env | ✅ in prod | `JWT_SECRET`, `CREDENTIAL_KEY` (to decrypt the resume), DB |
| **No Greenhouse API key** | — | it drives the **public embedded form**, not an API |

## 4. Required user profile fields
**Hard-gated by `profile_complete`:** `name`, `email`, `phone`, and a **real
uploaded, decryptable resume**.

**Additionally required by the real form (passed in `data.answers`, not auto-filled):**
the posting's **required screening questions** — typically first/last (derived from
`name`), **work authorization**, **visa sponsorship**, **"why this role" essay**,
**availability**, and **current/previous employer + title**. These are **not** in the
stored profile and must be **user-reviewed, truthful answers**; the system will not
fabricate them. Auto-fillable from profile: name, email, phone, resume,
LinkedIn/portfolio URLs.

## 5. Can it be safely tested locally?
**Yes — safely, against the controlled mock only.**
- **Safe:** `python -m tests.mock_greenhouse` (local form + confirmation server) +
  `python -m scripts.g3_controlled_test` → exercises the **real** submit → confirm →
  extract-id → evidence pipeline **without** contacting any employer or writing the
  DB. Read-only `python -m scripts.inspect_greenhouse <board> <gh_jid>` reaches a
  **real** form to verify field detection **without submitting**.
- **Prerequisites already met locally:** Chromium installed (`browser_available =
  True`); `live_ready()` flips to `True` with `JOBORA_LIVE=1`.
- **Not safe against a real employer:** pointing the live pipeline at a real
  posting **submits a real application** (irreversible; affects a real company and
  the user's candidacy). The project's standing integrity boundary is **never submit
  fabricated/test applications to real companies** — so local verification must use
  the **mock**, and a real submission must be a genuine, consented application by the
  actual user.

## 6. Step-by-step: submit ONE real Greenhouse application
_For a real, consenting user only, with truthful answers. Each run files one real
application._

1. **Profile ready:** the user is logged-in + approved, has uploaded a **real
   resume**, and has `name` + `email` + `phone` set (else the endpoint 400s).
2. **Pick a real Greenhouse posting** the user genuinely wants (note its `board` and
   `gh_jid`; the discovery feed provides `apply_url`, `external_id`, `fingerprint`).
3. **Inspect the form (read-only)** to see the required screening questions:
   `cd backend && python -m scripts.inspect_greenhouse <board> <gh_jid>`.
4. **Collect the user's truthful answers** to those required questions (work auth,
   visa, "why this role", availability, current employer/title) → an `answers`
   map keyed by the field names from step 3.
5. **Enable live mode** and ensure the worker runs: start the backend with
   `JOBORA_LIVE=1` (Chromium already installed; `INPROCESS_WORKER=1` default).
6. **Submit (explicit approval)** — one authenticated `POST /api/jobs/greenhouse/apply`
   as the user:
   ```json
   {
     "source": "Greenhouse",
     "apply_url": "https://boards.greenhouse.io/<board>/jobs/<gh_jid>",
     "external_id": "<gh_jid>",
     "fingerprint": "<job fingerprint>",
     "title": "...", "company": "...",
     "answers": { "<field_name>": "<user's truthful answer>", "...": "..." },
     "approved": true
   }
   ```
   Response: `{"submission_status":"Queued","application_id":N,...}`.
7. **The worker runs the real browser submit** (`live_ready` → `gh_apply`): fills
   identity + resume + the provided answers, clicks **Submit**, then detects the
   confirmation.
8. **Check the outcome** in the Activity Log or `GET /api/applications/{id}/evidence`:
   - **Verified Submitted** — confirmation + `GH-…` id + screenshot all captured, or
   - **Submitted** — confirmation + screenshot but no id (common on real Greenhouse), or
   - **CAPTCHA Required** / **Failed** — recorded with evidence, **not** a success.
9. The status is **only** "Verified Submitted" when all three proofs exist — the
   system enforces this; nothing is marked applied without evidence.

> **Honest caveats:** (a) a real posting's required screening questions will
> **reject** the submission if `answers` are missing/invalid; (b) real Greenhouse
> often shows **no application id**, so a successful real submission typically lands
> as **"Submitted"**, not "Verified Submitted"; (c) some boards present a captcha at
> submit → recorded as "CAPTCHA Required".

_No code was modified and no application was submitted in producing this report._
