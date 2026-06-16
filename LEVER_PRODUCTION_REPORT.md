# Lever — Production Report (Assisted Apply)

**Goal:** a complete, user-facing Lever apply flow that never claims "Applied"
without proof.

## Why Assisted (not unattended)
Every public Lever apply form ships an **hCaptcha** (verified in G1 on Ro +
Spotify). Unattended submission is therefore impossible/dishonest, so Lever runs
as **Assisted Apply**: Jobora does everything up to the captcha; the user clears
the captcha and submits; Jobora then captures and verifies the proof.

## Flow (implemented)
1. **Prefill + review** — `POST /api/jobs/assisted/prepare`
   - Builds a prefill packet from the user's **real profile** (name, email, phone,
     LinkedIn/GitHub/portfolio, location, resume) — no fabricated data.
   - Returns the genuine Lever apply URL + an hCaptcha notice + step instructions.
   - Records the job as **Manual Apply** (assisted). **Nothing is submitted.**
   - Enforces the plan's daily apply limit.
2. **User completes** the form (review/answer screening questions truthfully),
   clears the **hCaptcha**, and submits on the real Lever page.
3. **Record evidence** — `POST /api/jobs/assisted/record` (multipart)
   - Accepts `confirmation_url`, `reference_id`, and a confirmation `screenshot`.
   - Stores the screenshot via the storage layer; sets the evidence fields.

## Integrity gate (never "Applied" without proof)
`record` sets **Verified Submitted only if all three exist**: `application_id`
**and** `confirmation_url` **and** a stored screenshot (`evidence_available`).
With partial proof → **Submitted**; with none → stays **Manual Apply**. The
retired "Applied" label is never written. (Same gate as `app/status.py`.)

## Verification pipeline (already validated, G0–G3)
Form detection (9/9 core fields on real forms), resume upload, screening
questions, confirmation detection, reference-id extraction, evidence capture —
all PASS against the controlled mock (`tests/mock_lever.py`). See
`LEVER_{G1,G2,G3}_REPORT.md`.

## Status
| Item | State |
|---|---|
| Prefill from real profile | ✅ Complete |
| Review packet + apply URL + captcha notice | ✅ Complete |
| Daily-limit enforcement | ✅ Complete |
| Evidence capture + Verified-Submitted gate | ✅ Complete (backend) |
| Frontend wizard (prefill → review → record) | ⏳ **Partial** — endpoints ready; a guided UI component is the remaining work |
| Unattended auto-submit | ⛔ Not offered (hCaptcha) — by design |

**Verdict:** Lever Assisted Apply is **backend-complete and integrity-safe**;
the guided front-end wizard is the remaining piece before GA.
