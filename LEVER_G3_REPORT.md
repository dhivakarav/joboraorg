# Lever — G3 Submit Report (controlled mock)

**Phase:** G3 — click Submit, detect confirmation, extract reference id, capture
evidence, classify failures.
**Target:** a **controlled local mock** (`tests/mock_lever.py`) that mirrors the
real Lever DOM and confirmation flow. **No real employer was contacted. No DB row
was written.** This is the same integrity boundary used for Greenhouse G3 — we do
not file fabricated applications into a real company's ATS to test our code.
**Scope rule honored:** Greenhouse unchanged. `lever_submit.py` *reuses* the
already-verified Greenhouse detectors via import (7 success / 3 failure markers,
reference patterns) — confirmed the Greenhouse module is byte-for-byte untouched.

## Pipeline
`app/adapters/lever_submit.py` → `submit_application(form_url, fill, evidence_dir)`:
1. Load form, run caller `fill`, click Lever submit (`.template-btn-submit` /
   "Submit Application").
2. Wait for navigation; read final URL + title + body text.
3. **Failure markers checked first** (a failure must never read as success).
4. Success = Lever `/thanks` redirect **or** a success marker; then extract a
   reference id (`LVR-…` / generic patterns).
5. Save **screenshot + HTML snapshot + exact platform response** as evidence.

The mock reproduces three real outcomes, including the **hCaptcha** that every
public Lever form ships.

## Results (all three paths)

| Path | Submit clicked | Status | Confirmation | App ID | Evidence | DB action |
|---|---|---|---|---|---|---|
| **ok** | ✅ | **Applied** | ✅ Yes | ✅ `LVR-C7OPRIZCHU` | ✅ png+html | **WOULD set Applied** (confirmation + id + evidence all present) |
| **hCaptcha** | ✅ | **CAPTCHA Required** | ❌ No | — | ✅ png+html | **NO change** (not verified) |
| **validation** | ✅ | **Failed** | ❌ No | — | ✅ png+html | **NO change** (not verified) |

- Success confirmation URL: `…/mockco/thanks?ref=LVR-C7OPRIZCHU` (redirect detected).
- Evidence files written for every path under `/tmp/jobara_lever_g3/`
  (`success_*`, `captcha_*`, `validation_*` — screenshot + HTML snapshot each).

## Requirement #8 — "Never mark Applied unless confirmation + ID + evidence exist"
Enforced in the DB-gate check: `status == "Applied" AND confirmation_detected AND
application_id AND screenshot_path`. Only the **ok** path satisfies all four. The
**hCaptcha** and **validation** paths are recorded as failures with evidence and
produce **no** status change — no false success.

## The decisive real-world finding (carried to production verdict)
The **hCaptcha path is not hypothetical for Lever** — G1 confirmed that *every*
real public Lever apply form (Ro, Spotify) embeds an `h-captcha-response`. An
unattended bot click therefore lands on the hCaptcha challenge, which this
pipeline correctly classifies as **CAPTCHA Required → not Applied**. That is the
reason Lever cannot be promoted to fully-unattended auto-submit (see
`LEVER_PRODUCTION_READINESS.md`).

## G3 verdict
**PASS (pipeline).** Submit → confirmation detection → reference-id extraction →
evidence capture → failure classification all work, and the "Applied" gate is
correctly conditioned on confirmation + id + evidence. Validated against a
controlled mock only; real-company submission remains gated by hCaptcha.

_No real employer was contacted. No database record was created or updated._
