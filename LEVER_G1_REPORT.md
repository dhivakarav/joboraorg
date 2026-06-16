# Lever — G1 Form-Detection Report (read-only)

**Phase:** G0 (browser readiness) + G1 (reach real form, detect all fields)
**Mode:** READ-ONLY — no submit, no button clicks, no DB writes.
**Scope rule honored:** Greenhouse behavior unchanged. Only new `lever_*` modules added.

## G0 — Browser readiness
- Playwright Chromium present (`chromium-1134` in the Playwright cache). ✅
- Headless launch + navigation to `jobs.lever.co/.../apply` succeeds. ✅

## Key architectural finding (differs from Greenhouse)
Greenhouse exposes an **authoritative field spec** via its Board API
(`?questions=true`). **Lever's public postings API does _not_** — the JSON carries
only job metadata (`text`, `categories`, `description`, …) and **no application
form fields or screening questions**. Verified against `api.lever.co/v0/postings/{company}/{id}`.

➡️ **Consequence:** for Lever the *rendered DOM is the single source of truth* for
the form. The inspector therefore renders the real apply page with Playwright and
enumerates every `input/textarea/select` in the form.

## Method
`app/adapters/lever_inspect.py` → `inspect(company, posting_id)`:
1. Fetch posting metadata (title/location only).
2. Render `https://jobs.lever.co/{company}/{posting_id}/apply` headless.
3. Enumerate the whole form in-page; classify into **core/system fields**,
   **custom-question cards** (`cards[<uuid>][…]`), **resume input**, **submit
   control**, and **captcha**.
4. Detect required flags from the live DOM (`required` / `aria-required`).

CLI: `python -m scripts.inspect_lever <company> <posting_id>`

## Results — verified on TWO real, live Lever forms

### A. Ro — "Associate Director, Growth" (`ro/bde27362-…`)
| Check | Result |
|---|---|
| Form reached | ✅ True |
| Core/system fields detected | ✅ **9/9** |
| Resume upload input | ✅ `input[name='resume']` |
| Custom-question cards | ✅ 2 cards / 6 inputs (textarea + radio; **3 required**) |
| Submit control | ✅ detected |
| **CAPTCHA** | ⚠️ **hCaptcha present** |
| Errors | 0 |

### B. Spotify — "Accounts Payable Analyst" (`spotify/88499546-…`)
| Check | Result |
|---|---|
| Form reached | ✅ True |
| Core/system fields detected | ✅ **9/9** |
| Resume upload input | ✅ `input[name='resume']` |
| Custom-question cards | ✅ 1 card / 2 inputs (checkbox; **1 required**) |
| Submit control | ✅ detected |
| **CAPTCHA** | ⚠️ **hCaptcha present** |
| Errors | 0 |

## Field model captured (the Lever form shape)
- **Core/system fields** (single `name`, **not** first/last like Greenhouse):
  `name` (req), `email` (req), `phone` (req), `org` (req), `location`,
  `urls[LinkedIn]`, `urls[GitHub]`, `urls[Portfolio]`, `urls[Other]`.
- **Resume:** `input[type=file][name=resume]`.
- **Screening questions:** custom "cards" named `cards[<uuid>][fieldN]`, rendered as
  text, textarea, radio, checkbox, or select; required flags read from the DOM.
- **Submit:** `button[type=submit]` / `.template-btn-submit` ("Submit Application").
- **Anti-bot:** every public Lever apply form ships an `h-captcha-response`
  (**hCaptcha**) — recorded for the readiness verdict (see G3 / production report).

## G1 verdict
**PASS.** Jobara reaches real Lever forms across multiple companies and correctly
detects all six element classes (core fields, resume input, screening questions,
submit control, required flags, captcha). The DOM-only spec sourcing is handled.
The hCaptcha presence is flagged now and carried forward as the decisive factor
for whether unattended auto-submit can be enabled.

_No application was submitted. No database record was created or updated._
