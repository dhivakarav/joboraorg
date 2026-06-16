# Greenhouse G3 — Controlled Submission Test Report

## ⚠️ Submission target: controlled mock, NOT a real company

The requested test would have submitted a **fabricated application** (test
profile, placeholder answers) into **Stripe's real hiring system** — junk data a
real recruiter must triage, against Greenhouse/Stripe ToS, and the exact abuse
pattern auto-apply becomes at scale. I declined to file a fake application at a
real employer.

Instead, the **full G3 pipeline** (click Submit → detect confirmation → extract
application ID → save evidence → mark Applied only on confirmation → handle
CAPTCHA/validation failure) was validated against a **local mock Greenhouse form**
(`tests/mock_greenhouse.py`) that mirrors the real DOM ids and confirmation
flow. No real employer was contacted. No database row was written.

> For **real** submissions, the only acceptable use is *your own genuine
> application, with your real resume, to a job you actually want* — that ToS risk
> is yours to own. Jobora must never file applications you didn't author.

Code: `app/adapters/greenhouse_submit.py` · Mock: `tests/mock_greenhouse.py` ·
Runner: `scripts/g3_controlled_test.py`

---

## Test 1 — SUCCESS path (mock `/job/ok`)

| Field | Value |
|---|---|
| Job URL | `http://127.0.0.1:8099/job/ok` |
| Submit clicked | **Yes** |
| Submission result | **Applied** |
| Confirmation detected | **Yes** |
| Application ID | **`GH-KV3XR5NVH6`** (extracted from confirmation text) |
| Confirmation URL | `http://127.0.0.1:8099/confirmation?ref=GH-KV3XR5NVH6` |
| Screenshot | `/tmp/jobara_g3_evidence/success_confirmation.png` (24 KB, shows "Your application has been submitted!") |
| HTML snapshot | `/tmp/jobara_g3_evidence/success_snapshot.html` |
| Failure reason | (none) |
| DB action | **WOULD set status=Applied** (only because confirmation was detected) |

Exact platform response captured:
```
TITLE: Application submitted
URL:   http://127.0.0.1:8099/confirmation?ref=GH-KV3XR5NVH6
BODY:  Your application has been submitted!
       Thank you for applying. Your confirmation number is GH-KV3XR5NVH6.
```

## Test 2 — FAILURE path (mock `/job/captcha`)

| Field | Value |
|---|---|
| Job URL | `http://127.0.0.1:8099/job/captcha` |
| Submit clicked | **Yes** |
| Submission result | **Failed** |
| Confirmation detected | **No** |
| Application ID | (none) |
| Confirmation URL | `http://127.0.0.1:8099/submit?mode=captcha` |
| Screenshot | `/tmp/jobara_g3_evidence/captcha_confirmation.png` |
| HTML snapshot | `/tmp/jobara_g3_evidence/captcha_snapshot.html` |
| Failure reason | **CAPTCHA challenge** |
| DB action | **NO status change** (failure recorded, not success) |

Exact platform response captured:
```
TITLE: Verify
BODY:  Security check. Please complete the reCAPTCHA challenge to continue.
```

---

## Requirement compliance

| # | Requirement | Result |
|---|---|---|
| 1 | One test job only | ✅ one success + the failure-mode demo (req #9) |
| 2 | Dedicated test resume/profile | ✅ generated test PDF + test identity |
| 3 | Click Submit | ✅ clicks `#submit_app` |
| 4 | Detect confirmation page | ✅ success markers + URL |
| 5 | Extract application/confirmation ID | ✅ `GH-KV3XR5NVH6` |
| 6 | Save confirmation URL + screenshot + HTML | ✅ all three |
| 7 | Record exact platform response | ✅ title + URL + body excerpt |
| 8 | Mark Applied only if confirmed | ✅ Applied on success; Failed on CAPTCHA |
| 9 | CAPTCHA/validation/rejection → failed + evidence, no false success | ✅ CAPTCHA → Failed, evidence saved |

A bug found and fixed during the test: the ID regex initially over-matched and
returned a partial ID (`DV0FX`); corrected to extract the full token
(`GH-KV3XR5NVH6`).

---

## What this proves — and what it does NOT

**Proves:** the submit→confirm→extract→evidence→conditional-status logic is
correct and fail-safe (failures never report success).

**Does NOT prove (and must be validated before any real use):**
- Real Greenhouse confirmation pages differ per company; the success/ID regexes
  need validation against genuine confirmations.
- Real forms add reCAPTCHA, login walls, and per-posting required questions the
  mock doesn't replicate.
- No `Application` row is written yet — wiring a *verified* result into the DB is
  the integration step, gated to real authorized submissions only.

**Status: G3 logic validated on a controlled fixture. No real application was
submitted. Awaiting direction on a lawful real-submission path (your own genuine
application) before any production wiring.**
