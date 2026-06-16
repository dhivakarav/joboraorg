# Ashby — G1 Form-Detection Report (read-only)

**Phase:** G0 (browser readiness) + G1 (reach real SPA form, detect all fields).
**Mode:** READ-ONLY — no submit, no clicks beyond hydration, no DB writes.
**Scope rule honored:** Greenhouse **and** Lever unchanged. Only new `ashby_*`
modules added.

## G0 — Browser readiness
- Playwright Chromium present (`chromium-1134`). ✅
- Headless launch + navigation to `jobs.ashbyhq.com/.../application` succeeds, and
  the React SPA **hydrates** (waits for `#_systemfield_name` / submit button). ✅

## Architectural findings (Ashby differs from BOTH prior platforms)
1. **React SPA with no `<form>` element** (`has_form_element = False`, confirmed on
   Ramp + Linear). Field detection is scoped to the application pane, not a form.
2. **No API form spec** — like Lever, Ashby's public Posting API returns job
   metadata only. The **rendered DOM is the single source of truth**.
3. **System fields by id:** `#_systemfield_name`, `#_systemfield_email`,
   `#_systemfield_resume`; **phone is `input[type=tel]`**; custom questions are
   **UUID-named** inputs/textareas.
4. **Yes/No questions render as `<button>Yes</button>/<button>No</button>` pairs**
   (backed by a hidden checkbox), not radio inputs — they must be *clicked*.
5. **Anti-bot gate is Google reCAPTCHA** (`g-recaptcha-response`), present on every
   real form inspected.

## Method
`app/adapters/ashby_inspect.py` → `inspect(board, job_id)`: render the apply SPA,
wait for hydration, enumerate **all** `input/textarea/select` (no form scoping),
classify into system fields, resume input, UUID-named text questions, Yes/No
button questions, submit control, and captcha.

CLI: `python -m scripts.inspect_ashby <Board> <job_id>`

## Results — verified on TWO real, live Ashby forms

### A. Ramp — "Security Engineer, Cloud"
| Check | Result |
|---|---|
| Form reached (SPA hydrated) | ✅ True |
| `<form>` element | ✅ False (SPA, expected) |
| Core fields | ✅ name, email, **phone** (all required) |
| Resume upload | ✅ `#_systemfield_resume` |
| Text/textarea questions | ✅ 5 (**4 required**) |
| Yes/No button questions | ✅ 2 |
| Submit control | ✅ detected |
| **CAPTCHA** | ⚠️ **reCAPTCHA present** |
| Errors | 0 |

### B. Linear — "Senior / Staff Fullstack Engineer"
| Check | Result |
|---|---|
| Form reached (SPA hydrated) | ✅ True |
| `<form>` element | ✅ False (SPA, expected) |
| Core fields | ✅ name, email (this posting has no phone field) |
| Resume upload | ✅ `#_systemfield_resume` |
| Text/textarea questions | ✅ 9 (**7 required**) |
| Yes/No button questions | ✅ 1 |
| Submit control | ✅ detected |
| **CAPTCHA** | ⚠️ **reCAPTCHA present** |
| Errors | 0 |

## G1 verdict
**PASS.** Jobora reaches real Ashby SPA forms across companies and correctly
detects every element class — system fields, `tel` phone, resume input, UUID-named
text/textarea questions, Yes/No button questions, submit control, required flags,
and reCAPTCHA — despite the absence of a `<form>` element and any API spec. The
reCAPTCHA presence is flagged now and carried forward to the readiness verdict.

_No application was submitted. No database record was created or updated._
