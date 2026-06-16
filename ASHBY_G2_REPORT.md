# Ashby — G2 Fill + Validate Report (no submit)

**Phase:** G2 — fill every field class on a REAL Ashby SPA form and validate that
all required fields hold values.
**Mode:** Fill only. **Submit button never clicked. No DB record created/updated.**
**Scope rule honored:** Greenhouse + Lever unchanged; only new `ashby_*` modules.

## Method
`app/adapters/ashby_fill.py` → `fill_form(page, profile, resume_path)`:
1. Render the SPA and wait for hydration.
2. Fill **system fields** (`#_systemfield_name`, `#_systemfield_email`,
   `input[type=tel]`), **upload a resume** (`#_systemfield_resume`), answer every
   **UUID-named text/textarea/select** question, and **click "Yes"** on each Yes/No
   button question (SPA buttons, not radios).
3. Read the DOM back and validate **required-but-empty** fields (file inputs check
   `files.length`; Yes/No checked via the backing checkbox).
4. **Assert `submit_clicked is False`** before returning (hard G2 invariant).

CLI: `python -m scripts.fill_ashby <Board> <job_id>`

## Result — real form: Ramp "Security Engineer, Cloud"
| Check | Result |
|---|---|
| Form reached (SPA hydrated) | ✅ True |
| Resume uploaded | ✅ True (`#_systemfield_resume`, 1 file) |
| Yes/No questions answered | ✅ 2 (clicked "Yes") |
| **Required fields filled** | ✅ **8 / 8** |
| Submit clicked | ✅ **False** (invariant held) |
| Errors | 0 |
| Evidence | `…/Ramp_34413f8d_filled.png` (1280×3559 full-page PNG, 653 KB) |

### Required fields, all filled
`#_systemfield_name` ✅ · `#_systemfield_email` ✅ · phone `tel` ✅ ·
`#_systemfield_resume` (file) ✅ · 1 required `text` question ✅ ·
3 required `textarea` questions ✅.

Optional fields correctly left as-is: two extra file-upload questions (optional)
and an optional text field left blank; the two Yes/No questions (optional here)
were still answered to exercise the button-click path.

## SPA-specific handling proven
- **No `<form>` element** — fill targets loose inputs by id/UUID name. ✅
- **Yes/No buttons clicked**, not typed (2/2). ✅
- **`tel` phone** filled (Ashby does not use `_systemfield_phone`). ✅
- File input behind the "Upload File" widget accepted `set_input_files`. ✅

## G2 verdict
**PASS.** Every field class on a real Ashby SPA — system fields, resume upload,
UUID text/textarea questions, and Yes/No button questions — is populated and
validated required-complete (8/8), with the submit button never clicked and no DB
write. Full-page screenshot evidence saved.

_The form was NOT submitted. No database record was created or updated._
