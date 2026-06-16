# Real Submission Validation — Report (Phase 1)

**Goal:** Verify the Greenhouse pipeline against **real, eligible** internship /
fresher / new-grad jobs, and prove the "Verified Submitted" gate.
**Account:** `dhivakar271205@gmail.com` ("Dhivakar A V") — real resume on file.
**Integrity:** No fake jobs, no mock applications, no fabricated submissions or
evidence. Live submission is **OFF** (`JOBORA_LIVE` unset) and per-application
approval is required, so **0 real applications were sent** — that is reported
honestly, not as success.

## 1. Pipeline verification (G0–G3) — PASS
The Greenhouse submit pipeline was validated end-to-end against a controlled mock
(never a real employer): reach form → fill all fields + resume → submit → detect
confirmation → extract application id → capture evidence → classify failures
(CAPTCHA / validation → not Applied). See `GREENHOUSE_{G1,G2,G3}_REPORT.md`.

## 2. "Verified Submitted" gate — ENFORCED IN CODE
`app/status.py::evidence_complete()` + `queue.py` require **all three** before a
row can read "Verified Submitted":
1. **Confirmation page** reached (`confirmation_url` set), **and**
2. **Application ID** extracted (`application_id` non-empty), **and**
3. **Evidence screenshot** stored (`evidence_available = True`).

If any is missing, the worker **downgrades** "Verified Submitted" → "Submitted",
and the UI never shows "Applied". Verified live: across all 62 DB rows, **0** read
"Verified Submitted" (none have evidence) and **0** read "Applied" — correct.

## 3. Real eligible-jobs report (discovery + eligibility, read-only)

| Metric | Count |
|---|---|
| Greenhouse jobs fetched (real, live API) | **2,268** |
| Internship / entry-level **inspected** | **16** |
| **Eligible** for an early-career applicant | **10** |
| **Rejected** (senior / PhD-only / visa) | **6** |
| **Submitted** | **0** (live mode off + per-app approval required) |
| **Proof captured** | Pipeline + gate verified; per-submission proof captured only when you approve a real submission |

### Eligible (sample — passed the early-career eligibility filter)
- Stripe — Software Engineer, **Intern** (Great fit, 96)
- Stripe — **Software Engineering, New Grad** (Great fit, 96)
- Stripe — SWE **New Grad**, Developer Experience (Great fit, 96)
- Airbnb — Communications **Intern**, LATAM (Great fit, 88)
- …10 total

### Rejected — with machine-readable reason (the new eligibility engine)
| Role | Reason |
|---|---|
| Stripe — PhD Data Scientist, Intern (×2) | PhD-only role — requires an active PhD |
| Databricks — PhD GenAI Research Scientist Intern | PhD-only role — requires an active PhD |
| Instacart — ML Engineer, PhD Intern | PhD-only role — requires an active PhD |
| Instacart — ML PhD Intern, Economics | PhD-only role — requires an active PhD |
| Airbnb — Project Manager, Early Career | Senior/lead-level role — above an early-career stage |

## 4. Why "Submitted = 0" (honest)
Sending a real application requires: (a) **live mode** (`JOBORA_LIVE=1`),
(b) your **explicit per-application approval**, and (c) **your truthful answers**
to required screening questions (essay, work-authorization, visa) — which the
system will not fabricate under your name. None of the 10 eligible roles is also
a strong *domain + geography + timing* fit for an India-based 2027 grad (most
require US/AU work authorization or are New-Grad-now), so none was auto-submitted.

## Verdict
**Pipeline: VERIFIED. Verified-Submitted gate: ENFORCED (confirmation + ID +
screenshot, all three). Eligibility filter: WORKING (16 inspected → 10 eligible /
6 rejected with reasons). Real submissions: 0 (by design — no approval / live mode
/ fabricated answers).** No employer contacted; no DB row created; no proof
fabricated.
