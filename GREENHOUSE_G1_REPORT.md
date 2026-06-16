# Greenhouse G0-G1 — Test Report (detection only)

**Scope:** Prove Jobara can open a real Greenhouse application form, detect all
required fields, the resume upload input, and the screening questions.
**Constraints honored:** no submission, no submit-button click, no database
writes. Read-only inspection.

---

## G0 — Playwright setup & safe LIVE_MODE

| Item | Status | Evidence |
|---|---|---|
| Playwright package | ✅ installed | imports cleanly |
| Chromium browser | ✅ installed | launches: `Chromium 129.0.6668.29` |
| Dockerfile configured | ✅ | `playwright install --with-deps chromium` → shared `PLAYWRIGHT_BROWSERS_PATH=/ms-playwright`, readable by non-root `appuser` (build arg `INSTALL_BROWSERS=0` to skip) |
| Safe LIVE_MODE guard | ✅ | `app/adapters/runtime.py::live_ready()` |

Guard behavior (verified):
```
JOBORA_LIVE unset → live_ready() = (False, "JOBORA_LIVE is not set to 1 ...")
browser_available()                = True
JOBORA_LIVE=1     → live_ready() = (True, "live mode ready")
```
The Greenhouse **inspector is independent of LIVE_MODE** — it is read-only and
never submits, so it runs without enabling live mode. The existing submit path
(`adapters/base.py`) remains gated and untouched.

---

## G1 — Reach a real Greenhouse form & detect fields

**How it works (two sources, cross-checked):**
1. **Board API** `boards-api.greenhouse.io/v1/boards/{board}/jobs/{id}?questions=true`
   — authoritative spec of every field (name, type, required).
2. **Live render** of the embedded form `boards.greenhouse.io/embed/job_app?token={id}`
   via Playwright — confirms each field is present/reachable in the DOM
   (iframe-aware: switches into `#grnhse_iframe` when present; these postings
   serve the form top-level, so no iframe was needed).

Run: `python -m scripts.inspect_greenhouse <board> <job_id>`

### Test 1 — stripe / 7964697
```
Job          : Account Executive, AI Sales  [stripe/7964697]
Location     : San Francisco, CA
Form URL     : https://boards.greenhouse.io/embed/job_app?token=7964697
Form reached : True   |   via iframe: False

CORE FIELDS (API-declared → detected in live DOM):
  [OK ] first_name   input_text  required  (#first_name)
  [OK ] last_name    input_text  required  (#last_name)
  [OK ] email        input_text  required  (#email)
  [OK ] phone        input_text  required  (#phone)
  [MISS] resume_text       textarea optional   (collapsed paste-mode alt — see note)
  [MISS] cover_letter_text textarea optional   (collapsed paste-mode alt — see note)

RESUME UPLOAD:
  declared by API : True
  input detected  : True  (via input#resume)

SCREENING QUESTIONS (11 declared):
  [OK ] question_67255025  input_text                 required | current/previous employer
  [OK ] question_67255026  input_text                 required | current/previous job title
  [OK ] question_67255027  multi_value_single_select  required | country you currently work in
  [OK ] question_67255028[] multi_value_multi_select  required | country/countries ...
  [OK ] question_67255029  multi_value_single_select  required | authorized to work ...
  [OK ] question_67255030  multi_value_single_select  required | require sponsorship ...
  [OK ] question_67255031  multi_value_single_select  required | hybrid/office option ...
  [OK ] question_67255032  multi_value_single_select  required | previously employed by Stripe
  [OK ] question_67255033  input_text                 required | most recent school
  [OK ] question_67255034  input_text                 required | most recent degree
  [OK ] question_67358470  input_text                 required | located in Bay Area

ERRORS: 0
SUMMARY: form_reached=True | core 4/6 | resume True | questions 11/11 | errors 0
```

### Test 2 — stripe / 7532733
```
Job          : Account Executive, AI Sales  [stripe/7532733]
Form reached : True   |   via iframe: False
SUMMARY: form_reached=True | core 4/6 | resume True | questions 10/10 | errors 0
```

---

## Interpretation

- ✅ **Form reached** on a real, live Greenhouse posting (not a demo).
- ✅ **All required text fields** (`first_name`, `last_name`, `email`, `phone`) located by stable `#id` selectors.
- ✅ **Resume upload input detected** (`input#resume`) — the real hidden file input behind the "Attach" widget.
- ✅ **All screening questions detected** (11/11 and 10/10), including `multi_value_single_select` / `multi_value_multi_select` dropdowns and `[]` array fields.
- ✅ **Zero errors.**

**Note on the two `MISS` rows:** `resume_text` and `cover_letter_text` are
Greenhouse's *optional* "paste instead of upload" textareas. They are collapsed
in the DOM until the applicant toggles paste-mode, so they are correctly absent
on initial render. The resume **file** path (`input#resume`) — the one we'd
actually use — is detected. This is expected, not a failure.

---

## What is NOT done (waiting for approval — Phase G2+)
- Filling any field, uploading the resume, answering questions.
- Clicking submit / submitting anything.
- Confirmation-page detection and application-ID extraction.
- Any database status change.

The submit path stays gated; nothing in this phase can submit. **Awaiting
approval to proceed to G2 (fill) and G3 (submit + verify + capture ID).**
