# Greenhouse G2 — Fill & Validate Report (NO submission)

**Scope:** Fill every detected field, upload the resume, answer screening
questions by type, validate required fields, capture screenshots.
**Hard constraints (verified in code):** Submit is **never** clicked (no submit
code path exists in the filler), and the **database is never touched** (zero model
imports). The gated submit path in `adapters/base.py` is unchanged.

Module: `app/adapters/greenhouse_fill.py` · Runner: `python -m scripts.fill_greenhouse`

---

## Field-type handling implemented
| Greenhouse type | How it's filled | Validated by |
|---|---|---|
| `input_text` | `.fill(value)` on `#<name>` | reading `input_value()` back |
| `textarea` | `.fill(value)` | `input_value()` |
| `input_file` (resume) | `set_input_files(resume.pdf)` on `input#resume` | upload confirmed |
| `multi_value_single_select` (dropdown) | **react-select**: click combobox → type → pick option | `.select__single-value` chip present |
| `multi_value_multi_select` | react-select multi: select an option | `.select__multi-value__label` chip |
| native `<select>` | `select_option` | — |
| radio button | `.check()` first option | `:checked` present |
| checkbox | `.check()` | `:checked` present |

Greenhouse renders dropdowns as **react-select** widgets (not native `<select>`),
so selection is click-to-open + choose-option, and validation reads the rendered
value chip — not just "we clicked something."

---

## Results — 3 real live Greenhouse jobs

| Job | Form loaded | Resume uploaded | Core fields | Questions answered | Missing required | Errors |
|---|---|---|---|---|---|---|
| stripe/7964697 — Account Executive, AI Sales | ✅ | ✅ | 4/4 | **11/11** | **0** | 0 |
| stripe/7532733 — Account Executive, AI Sales | ✅ | ✅ | 4/4 | **10/10** | **0** | 0 |
| stripe/7954688 — Account Executive, AI Sales (Grower) | ✅ | ✅ | 4/4 | **10/10** | **0** | 0 |

All three: **every required field satisfied, zero validation errors.** The
required fields include react-select dropdowns (country of residence, work
authorization, sponsorship, etc.) — validated by reading their rendered value
chips back from the DOM.

### Screenshots (full-page, captured per job)
For each job, three stages saved to `/tmp/jobara_g2_shots/`:
- `*_01_form_loaded.png` — blank form on load
- `*_02_resume_uploaded.png` — after resume attached
- `*_03_fields_filled.png` — all fields + questions populated (visually confirmed:
  name/email/phone filled, dropdowns showing selected values, screening answers in)

Example (stripe/7964697): `01` 738 KB → `03` 780 KB — the filled screenshot is
larger, consistent with populated selects expanding layout.

---

## Test data used
- Profile: Priya Menon / priya.menon@example.com / +1 415 555 0142
- Resume: generated test PDF
- Text questions answered with a clear placeholder ("N/A — automated form-fill
  validation test"); dropdowns picked an affirmative/valid option (prefers
  "Yes"/"United States", else first valid value from the API spec).

---

## Constraints honored (code-verified)
- ❌ **No submit** — only `submit` references in the filler are doc/log strings;
  grep for a submit-button click → **NONE**.
- ❌ **No DB writes** — `grep models|SessionLocal|Application` in filler → **0**.
- ✅ Required-field validation runs before stopping.
- ✅ Screenshots after form-load, resume-upload, fields-filled.

---

## NOT done (awaiting approval — G3)
- Clicking Submit / submitting any application.
- Confirmation-page detection.
- Application-ID extraction.
- Any DB status change.

**Stopped before submission as instructed. Awaiting approval for G3.**
