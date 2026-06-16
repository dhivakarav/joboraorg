# Lever — G2 Fill + Validate Report (no submit)

**Phase:** G2 — fill every field class on a REAL Lever form and validate that all
required fields hold values.
**Mode:** Fill only. **Submit button never clicked. No DB record created/updated.**
Filling inputs client-side does not create an application.
**Scope rule honored:** Greenhouse behavior unchanged; only new `lever_*` modules.

## Method
`app/adapters/lever_fill.py` → `fill_form(page, profile, resume_path)`:
1. Render the live apply form.
2. Enumerate the form (DOM is authoritative for Lever — no API spec).
3. Fill **core/system fields** (`name`, `email`, `phone`, `org`, `location`,
   `urls[...]`), **upload a resume** (`input[type=file]`), and **answer every
   custom-question card** (`cards[<uuid>][…]`): textarea, text, radio, checkbox,
   and select are each handled.
4. Read the DOM back and validate **required-but-empty** fields (radio/checkbox
   groups collapse to "filled if any member checked"; file inputs check
   `files.length`).
5. **Assert `submit_clicked is False`** before returning (hard G2 invariant).

CLI: `python -m scripts.fill_lever <company> <posting_id>`

## Result — real form: Ro "Associate Director, Growth"
| Check | Result |
|---|---|
| Form reached | ✅ True |
| Resume uploaded | ✅ True (`input[name='resume']`, 1 file) |
| **Required fields filled** | ✅ **7 / 7** |
| Submit clicked | ✅ **False** (invariant held) |
| Errors | 0 |
| Evidence | `…/ro_bde27362_filled.png` (1280×3964 full-page PNG, 271 KB) |

### Per-field outcome (required ones)
| Field | Kind | Required | Filled |
|---|---|---|---|
| `name` | text | ✅ | ✅ "Test Candidate" |
| `email` | email | ✅ | ✅ "g2.test@example.com" |
| `phone` | text | ✅ | ✅ "+1 415 555 0100" |
| `org` | text | ✅ | ✅ "Independent" |
| `cards[06e54799…]` (Q1) | textarea | ✅ | ✅ answered |
| `cards[06e54799…]` (Q3) | textarea | ✅ | ✅ answered |
| `cards[c8cb8fa2…]` | radio | ✅ | ✅ checked |

Optional fields handled correctly: `urls[LinkedIn/GitHub/Portfolio]` filled; the
optional textarea answered; demographic fields (`pronouns`, `eeo[gender/race/
veteran]`) intentionally left blank.

### One nuance documented
`location` is a Lever **autocomplete** widget: a plain `fill()` value is cleared
on blur unless a dropdown suggestion is selected. On this posting `location` is
**optional**, so it does not affect the result. For any posting where `location`
is required, the fill step must select a suggestion from the autocomplete dropdown
(a small enhancement, not a blocker — noted for the production path).

## G2 verdict
**PASS.** All field classes — core fields, resume upload, and required screening
questions (textarea + radio) — are populated on a real Lever form, validated
required-complete (7/7), with the submit button never clicked and no DB write.
Full-page screenshot evidence saved.

_The form was NOT submitted. No database record was created or updated._
