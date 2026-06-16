# Ashby — Production Readiness Report (G0–G3)

**Question:** Has Ashby passed the same six submission-verification gates as
Greenhouse, including React-SPA success handling, and can auto-apply be enabled?

**Short answer:** The Ashby submit **pipeline is verified end-to-end, including
SPA in-place confirmation detection** (form detection, resume upload, screening
questions, DOM-state confirmation, reference-id extraction, evidence). But
**fully-unattended auto-apply is NOT enabled**, because **every real Ashby apply
form embeds Google reCAPTCHA** that a bot cannot lawfully or reliably solve. The
honest production mode for Ashby is **Assisted Apply** (Jobora prefills the SPA;
the user clears reCAPTCHA and submits; Jobora verifies + captures evidence).

## The six gates (+ SPA requirement)

| # | Gate | Status | Where proven |
|---|---|---|---|
| 1 | Real form detection | ✅ PASS | G1 — Ramp + Linear, SPA hydrated, all classes detected |
| 2 | Resume upload | ✅ PASS | G1 (`#_systemfield_resume`) + G2 (file uploaded) |
| 3 | Screening questions | ✅ PASS | G1 + G2 (UUID text/textarea **and** Yes/No buttons) |
| 4 | Confirmation-state detection | ✅ PASS | G3 — **DOM-state**, `url_changed=False` |
| 5 | Application-id extraction | ✅ PASS | G3 (`ASH-B5PLTZUK4V` extracted) |
| 6 | Submission evidence | ✅ PASS | G2 + G3 (screenshot + HTML snapshot + response) |
| 7 | **React-SPA success state** | ✅ PASS | G3 confirmation detected with **no navigation** |

All gates pass at the **pipeline** level. Gates 4–7 were validated against a
**controlled mock SPA** (never a real employer), exactly as Greenhouse G3 was.

## Why auto-apply is still NOT enabled (the gating reason)
- **reCAPTCHA on 100% of forms.** G1 found `g-recaptcha-response` on every real
  Ashby form inspected (Ramp, Linear). Like Lever's hCaptcha, it is shipped by
  default.
- An unattended submit lands on the reCAPTCHA challenge, which the pipeline
  classifies as **CAPTCHA Required → not Applied** (proven in G3). We will **not**
  attempt captcha-solving.
- **No API field/submit spec.** Ashby's public Posting API exposes no form fields
  and no submit channel; the only path is the captcha-gated SPA.

## Decision (integrity-preserving)
- **Keep `supports_auto_submit = False`, `manual_only = True`** for the Ashby
  adapter — **unchanged**, not flipped. Greenhouse (`auto_submit = True`) and Lever
  remain untouched; the Greenhouse detector module is reused read-only.
- **Recommended product mode: Assisted Apply.** Jobora uses the verified G1/G2
  prefill to populate the whole Ashby SPA (system fields + resume + UUID questions
  + Yes/No buttons), then hands off for the human to clear reCAPTCHA and submit.
  G3 DOM-state detection then confirms the outcome and stores evidence.
- **Requirement #8 upheld:** nothing is marked "Applied" without confirmation +
  reference id + evidence — verified in code and in the G3 failure paths.

## What would unlock fully-unattended auto-apply (not pursued)
- An **authorized integration** (Ashby's partner/Apply API with credentials and
  consent) that bypasses the public reCAPTCHA-gated SPA. Until such a channel
  exists, fully-unattended auto-apply stays off.

## Evidence index
- G1: `ASHBY_G1_REPORT.md` (Ramp + Linear; SPA, no `<form>`, reCAPTCHA flagged).
- G2: `ASHBY_G2_REPORT.md` + `/tmp/jobara_ashby_g2/Ramp_*_filled.png` (8/8 required,
  Yes/No buttons clicked).
- G3: `ASHBY_G3_REPORT.md` + `/tmp/jobara_ashby_g3/{success,captcha,validation}_*`
  (DOM-state confirmation, `url_changed=False`).
- Code (new, additive): `app/adapters/ashby_inspect.py`, `ashby_fill.py`,
  `ashby_submit.py`; `scripts/inspect_ashby.py`, `fill_ashby.py`,
  `g3_ashby_test.py`, `mock_ashby.py`.
- Regression: **21/21 backend tests pass**; Greenhouse + Lever capabilities unchanged.

## Verdict
**Ashby submit pipeline (incl. SPA success handling): VERIFIED. Auto-apply: NOT
enabled (reCAPTCHA-gated). Production mode: Assisted Apply (prefill + human
captcha/submit + verified evidence).** Same standard Greenhouse met, applied
honestly to a React-SPA platform whose real forms carry a mandatory
human-verification step.
