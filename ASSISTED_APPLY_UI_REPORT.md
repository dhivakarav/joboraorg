# Assisted Apply Wizard — Report (Critical C1)

Closes the Critical finding: Lever/Ashby assisted apply now has a complete
front-end. No matching/integrity/pipeline logic was changed.

## Flow
Clicking **Apply** on a Lever or Ashby job opens the **Assisted Apply Wizard**
(`frontend/src/components/AssistedApplyWizard.jsx`); Greenhouse and others keep the
existing review modal (routed in `FindJobs.jsx` via `ASSISTED_PLATFORMS`).

### Step 1 — Review (calls `POST /api/jobs/assisted/prepare`)
- **Portal type** shown (`Lever · Assisted` / `Ashby · Assisted`).
- **Resume being used** — real filename (📄), or a clear "upload one first" block.
- **Required fields** — Full name · Email · Phone · Resume · LinkedIn · Portfolio,
  each **prefilled from the user's real profile** (no fabrication). Empty required
  fields are flagged "— add on portal".
- **Screening questions** — an explicit note that the posting may ask work-auth /
  "why this role" questions to answer **truthfully on the portal**; Jobora never
  auto-fills answers under the user's name.
- **Captcha note** — hCaptcha (Lever) / reCAPTCHA (Ashby).
- **"Open {portal} application ↗"** opens the real apply URL in a new tab.

### Step 2 — Apply & record (calls `POST /api/jobs/assisted/record`)
- Numbered instructions (fill screening Qs → complete captcha → submit).
- **Evidence capture:** confirmation URL + reference/application ID + screenshot
  upload (multipart via the new `api.postForm`).
- Result shows the resulting **StatusBadge** + exactly which proof is missing.

## Status correctness (integrity preserved)
The backend gate (unchanged) sets **Verified Submitted only when application ID +
confirmation URL + screenshot all exist**; partial proof → **Submitted**; none →
stays **Manual Apply**. The wizard surfaces the `missing[]` list so the user knows
why it isn't fully verified. "Applied" is never shown.

## Bug fixed along the way
`_prefill_from_profile` referenced keys that don't exist in `load_profile`
(`full_name`/`linkedin`/`portfolio`) → prefill came back blank. Now mapped to the
real keys (`name`/`linkedin_url`/`portfolio_url`/`location`) and the resume
filename. Verified: profile → `{full_name:'Dhivakar A V', linkedin:'…', resume_filename:'…'}`.

## Backend additions to support the UI
`/prepare` now returns `required_fields` (prefilled), `resume_filename`,
`captcha`, `screening_note`, and step `instructions`. `api.postForm()` added for
multipart evidence upload.

## Verification
- Frontend builds clean; 21/21 backend tests pass; endpoints live.
- Resume-gate behaves correctly (no resume → 400 "Upload a resume before applying"
  → wizard shows the upload prompt).
- Routing verified: Lever/Ashby → wizard; Greenhouse → review modal.

## Known limitation (honest)
Per-posting screening questions are **not** enumerated live in the wizard (that
needs a ~15–20s headless inspection per job). Instead the wizard shows the
standard required fields + a truthful note to complete screening questions on the
portal. This keeps the wizard fast and never fabricates answers.
