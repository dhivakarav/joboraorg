# Ashby — G3 Submit Report (controlled mock, React-SPA aware)

**Phase:** G3 — click Submit, detect the **in-app SPA confirmation by DOM state**,
extract reference id, capture evidence, classify failures.
**Target:** a **controlled local mock SPA** (`tests/mock_ashby.py`) that mirrors
real Ashby and — critically — renders its result **in place with NO navigation**
(the URL never changes). **No real employer was contacted. No DB row was written.**
**Scope rule honored:** Greenhouse + Lever unchanged. `ashby_submit.py` *reuses*
the verified Greenhouse detectors via import; both prior modules are untouched.

## Requirement #7 — handling React-SPA success states
Real Ashby does not navigate to a `/thanks` page; it swaps the application pane
for a success panel client-side. The pipeline therefore **polls the DOM** after
the submit click (up to ~12s) and detects confirmation by:
1. an **in-app success container** (`[class*='application-form-success']`,
   `.application-success`), or
2. **success text** ("application submitted" / "thank you for applying" / …).

Failure markers (reCAPTCHA, validation) are checked **first** each poll so a
failure can never read as success.

## Pipeline
`app/adapters/ashby_submit.py` → `submit_application(form_url, fill, evidence_dir)`:
load SPA → caller `fill` → click "Submit Application" → **poll DOM state** →
classify → extract `ASH-…`/generic reference → save screenshot + HTML snapshot +
exact response text.

## Results (all three paths)

| Path | Submit | URL changed | Status | Confirmation | App ID | Evidence | DB action |
|---|---|---|---|---|---|---|---|
| **ok** | ✅ | **False** | **Applied** | ✅ via `dom-state(container)` | ✅ `ASH-B5PLTZUK4V` | ✅ png+html | **WOULD set Applied** (confirmation + id + evidence) |
| **reCAPTCHA** | ✅ | False | **CAPTCHA Required** | ❌ | — | ✅ png+html | **NO change** |
| **validation** | ✅ | False | **Failed** | ❌ | — | ✅ png+html | **NO change** |

- **`url_changed=False` on every path**, yet the success path is still correctly
  confirmed — proving SPA DOM-state detection works (requirement #7).
- Evidence under `/tmp/jobara_ashby_g3/` (`success_*`, `captcha_*`, `validation_*`
  — screenshot + HTML snapshot each).

## Requirement #8 — "Never mark Applied unless confirmation + ID + evidence exist"
The DB-gate is `status == "Applied" AND confirmation_detected AND application_id
AND screenshot_path`. Only the **ok** path satisfies all four; **reCAPTCHA** and
**validation** are recorded as failures with evidence and produce no status change.

## Real-world finding (carried to production verdict)
G1 confirmed **every real Ashby form embeds Google reCAPTCHA**
(`g-recaptcha-response`). An unattended submit lands on the reCAPTCHA challenge,
which this pipeline classifies as **CAPTCHA Required → not Applied** (proven in
G3). That is the reason Ashby cannot be promoted to fully-unattended auto-submit.

## G3 verdict
**PASS (pipeline).** SPA submit → DOM-state confirmation detection →
reference-id extraction → evidence capture → failure classification all work, and
the "Applied" gate is correctly conditioned on confirmation + id + evidence.
Validated against a controlled mock only; real-company submission remains gated by
reCAPTCHA.

_No real employer was contacted. No database record was created or updated._
