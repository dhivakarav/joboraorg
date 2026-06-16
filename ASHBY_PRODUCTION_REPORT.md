# Ashby — Production Report (Assisted Apply)

**Goal:** a complete, user-facing Ashby apply flow with React-SPA confirmation
handling that never claims "Applied" without proof.

## Why Assisted (not unattended)
Every real Ashby apply form ships **Google reCAPTCHA** (verified in G1 on Ramp +
Linear), and the form is a **React SPA** with **no `<form>` element** that shows
its success **in-app with no URL change**. Unattended submission is therefore
impossible/dishonest → Ashby runs as **Assisted Apply**.

## Flow (implemented)
1. **Prefill + review** — `POST /api/jobs/assisted/prepare`
   - Prefill packet from the user's **real profile** (no fabrication).
   - Returns the genuine Ashby apply URL + a reCAPTCHA / in-app-success notice.
   - Records the job as **Manual Apply** (assisted). **Nothing is submitted.**
2. **User completes** the SPA form (system fields, resume, UUID questions, Yes/No
   buttons), clears the **reCAPTCHA**, and submits.
3. **Record evidence** — `POST /api/jobs/assisted/record`
   - Accepts `confirmation_url`, `reference_id` (`ASH-…`), and a confirmation
     `screenshot`; stores it and sets the evidence fields.

## React-SPA confirmation detection (validated)
The G3 pipeline detects Ashby's success **by DOM state** (in-app success panel),
not by URL change (`url_changed=False`), and extracts the `ASH-…` reference. See
`ASHBY_G3_REPORT.md` (validated against `tests/mock_ashby.py`). For Assisted
Apply, the user's captured confirmation screenshot + reference id are the proof.

## Integrity gate (never "Applied" without proof)
**Verified Submitted only if** `application_id` + `confirmation_url` + stored
screenshot all exist; partial → **Submitted**; none → **Manual Apply**. "Applied"
is never written.

## Verification pipeline (already validated, G0–G3)
SPA form detection (Ramp + Linear; no `<form>`), resume upload, UUID + Yes/No
questions, DOM-state confirmation, `ASH-…` id extraction, evidence — all PASS.
See `ASHBY_{G1,G2,G3}_REPORT.md`.

## Status
| Item | State |
|---|---|
| Prefill from real profile | ✅ Complete |
| Review packet + apply URL + reCAPTCHA / SPA notice | ✅ Complete |
| SPA confirmation handling (pipeline) | ✅ Complete (DOM-state) |
| Evidence capture + Verified-Submitted gate | ✅ Complete (backend) |
| Frontend wizard | ⏳ **Partial** — endpoints ready; guided UI is remaining |
| Unattended auto-submit | ⛔ Not offered (reCAPTCHA) — by design |

**Verdict:** Ashby Assisted Apply is **backend-complete and integrity-safe**;
the guided front-end wizard is the remaining piece before GA.
