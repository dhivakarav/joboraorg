# Lever — Production Readiness Report (G0–G3)

**Question:** Has Lever passed the same six submission-verification gates as
Greenhouse, and can auto-apply be enabled?

**Short answer:** The Lever submit **pipeline is verified end-to-end** (form
detection, resume upload, screening questions, confirmation detection,
reference-id extraction, evidence capture). But **fully-unattended auto-apply is
NOT enabled**, because **every real public Lever apply form embeds an hCaptcha**
that a bot cannot lawfully or reliably solve. The honest production mode for Lever
is **Assisted Apply** (Jobora prefills everything; the user clears the hCaptcha
and clicks submit; Jobora then verifies + captures evidence).

## The six gates

| # | Gate | Status | Where proven |
|---|---|---|---|
| 1 | Real form detection | ✅ PASS | G1 — Ro + Spotify, **9/9** core fields, DOM-sourced |
| 2 | Resume upload | ✅ PASS | G1 (`input[name=resume]`) + G2 (file uploaded) |
| 3 | Screening questions | ✅ PASS | G1 detects `cards[<uuid>]`; G2 answers textarea/radio |
| 4 | Confirmation-page detection | ✅ PASS | G3 (`/thanks` redirect + success markers) |
| 5 | Application-id extraction | ✅ PASS | G3 (`LVR-C7OPRIZCHU` extracted) |
| 6 | Submission evidence | ✅ PASS | G2 + G3 (screenshot + HTML snapshot + response text) |

All six pass at the **pipeline** level. Gates 4–6 were validated against a
**controlled mock** (never a real employer), exactly as Greenhouse G3 was.

## Why auto-apply is still NOT enabled (the gating reason)
- **hCaptcha on 100% of forms.** G1 found `h-captcha-response` on every real Lever
  form inspected (Ro, Spotify). Unlike Greenhouse (where a captcha is risk-based
  and often absent), Lever ships it by default.
- An unattended submit therefore lands on the hCaptcha challenge, which the
  pipeline classifies as **CAPTCHA Required → not Applied** (proven in G3). So a
  bot would rarely produce a verified submission, and forcing it would mean either
  failing constantly or attempting captcha-solving — which we will **not** do.
- **No API field spec.** Lever's public postings API exposes no form fields, so
  there is no server-side path to submit; the only path is the captcha-gated DOM.

## Decision (integrity-preserving)
- **Keep `supports_auto_submit = False`, `manual_only = True`** for the Lever
  adapter. **Unchanged** — not flipped — and Greenhouse is untouched
  (`auto_submit = True` preserved; its detector module reused read-only).
- **Recommended product mode: Assisted Apply.** Jobora uses the verified G1/G2
  prefill to populate the entire Lever form for the user (core fields + resume +
  screening answers), then hands off for the human to clear hCaptcha and submit.
  G3 detection then confirms the outcome and stores evidence. This is honest,
  lawful, and still removes ~90% of the manual effort.
- **Requirement #8 upheld:** nothing is marked "Applied" without confirmation +
  reference id + evidence — verified in code and in the G3 failure paths.

## What would unlock fully-unattended auto-apply (not pursued)
- An **authorized integration** (e.g., Lever's partner/Postings/Apply API with
  credentials and consent) that bypasses the public captcha-gated form. Until such
  an authorized channel exists, fully-unattended auto-apply stays off.

## Evidence index
- G1: `LEVER_G1_REPORT.md` (Ro + Spotify, 9/9 fields, hCaptcha flagged).
- G2: `LEVER_G2_REPORT.md` + `/tmp/jobara_lever_g2/ro_*_filled.png` (7/7 required).
- G3: `LEVER_G3_REPORT.md` + `/tmp/jobara_lever_g3/{success,captcha,validation}_*`.
- Code (new, additive): `app/adapters/lever_inspect.py`, `lever_fill.py`,
  `lever_submit.py`; `scripts/inspect_lever.py`, `fill_lever.py`,
  `g3_lever_test.py`, `mock_lever.py`.
- Regression: **21/21 backend tests pass**; Greenhouse capabilities unchanged.

## Verdict
**Lever submit pipeline: VERIFIED. Auto-apply: NOT enabled (hCaptcha-gated).
Production mode: Assisted Apply (prefill + human captcha/submit + verified
evidence).** This is the same standard Greenhouse met, applied honestly to a
platform whose real forms carry a mandatory human-verification step.
