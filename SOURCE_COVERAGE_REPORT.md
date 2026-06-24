# Source Coverage & Success-Rate Report

Focus sources: **Greenhouse, Lever, Ashby, Workable, Wellfound, JSearch**
(Remotive/Arbeitnow/Adzuna/Jooble/Internshala also run in the aggregator and are
noted where relevant). Generated from live runs against the running stack.

---

## 1. Discovery coverage (live, query = "machine learning engineer")

| Source     | Status (runtime)   | Jobs fetched | API type            | Why |
|------------|--------------------|--------------|---------------------|-----|
| Greenhouse | Connected          | **2273**     | Official public API | Multi-board public job API — no key |
| Ashby      | Connected          | **410**      | Official public API | Public posting API — no key |
| Lever      | Connected          | **226**      | Official public API | Public postings API — no key |
| Workable   | Disabled           | 0            | Account API         | Needs an authorized account token (`WORKABLE_*`) |
| JSearch    | Connected¹         | 0            | RapidAPI (key)      | Pointed at local mock; needs a real `JSEARCH_API_KEY` |
| Wellfound  | Disabled           | 0            | No public API       | Needs an authorized/licensed feed |

**~2,900 real jobs reachable** from the three official-API sources — well past the
100-job target. ¹ JSearch reports "Connected" only because dev `.env` points it at the
mock host with a placeholder key.

## 2. Capability matrix

| Source     | Discovery | Apply             | Auto Apply                         | API Access |
|------------|-----------|-------------------|------------------------------------|------------|
| Greenhouse | ✅ live   | ✅ form adapter    | ✅ live browser submit (JOBORA_LIVE) | ✅ |
| Lever      | ✅ live   | ✅ assisted        | ⚠️ assisted (hCaptcha) — prefill, user submits | ✅ |
| Ashby      | ✅ live   | ✅ assisted        | ⚠️ assisted (reCAPTCHA) — prefill, user submits | ✅ |
| Workable   | 🔑 needs token | ✅ assisted   | ⚠️ assisted                        | ✅ |
| Wellfound  | 🔑 needs feed  | ✅ generic     | ❌ manual                           | ❌ |
| JSearch    | 🔑 needs key   | ✅ generic     | ❌ aggregator (links out)           | ✅ |

## 3. End-to-end auto-apply verification (this run)

- **Greenhouse** — submit endpoint gates verified (`approved=false` → HTTP 400). Real
  browser submission runs via the background queue (same path proven end-to-end with
  the Internshala mock harness). Not fired against a real company in testing.
- **Lever** — assisted `prepare` against a **real** posting (`jobs.lever.co/voodoo/…`):
  prefilled the profile, flagged hCaptcha, **no submission**. ✅
- **Ashby** — assisted `prepare` against a **real** posting (`jobs.ashbyhq.com/Ramp/…`):
  prefilled, flagged reCAPTCHA, **no submission**. ✅
- **Workable / Wellfound / JSearch** — discovery-/link-only here (no live auto-submit).

## 4. Observed submission outcomes (success rate, test DB)

Counts of `submission_status` per platform across all applications recorded during
testing. "Success" = `Submitted` or `Verified Submitted`; `Draft`/`Manual Apply` are
tracked-but-not-submitted (expected for assisted/manual platforms).

| Platform   | Submitted | Verified | Manual/Draft | Submit success (of attempts) |
|------------|-----------|----------|--------------|------------------------------|
| Greenhouse | 5         | 1        | 126 draft    | 6/6 attempts succeeded¹       |
| Internshala| 1         | 1        | 1            | 2/2 attempts (mock harness)   |
| Lever      | 0         | 0        | 5 manual     | n/a — assisted (user submits) |
| Ashby      | 0         | 0        | 30           | n/a — assisted (user submits) |
| Company Career Page | 0| 0        | 75           | n/a — manual                  |
| LinkedIn   | 0         | 0        | 4 manual     | n/a — manual                  |

¹ Draft rows are decorated/tracked jobs that were never submitted (the normal state
for browse/track). Of the applications actually *submitted*, all reached
Submitted/Verified. Note: real Greenhouse browser submits were not fired at real
companies in testing — the mechanism is shared with the verified Internshala path.

## 5. Resume ranking (AI/ML profile)

Aggregated **100 real jobs**, fully deduped (100/100 unique fingerprints **and** apply
URLs), ranked by an AI/ML resume (Python, ML, DL, TensorFlow/PyTorch, NLP, CV, …).
Top matches surfaced correctly: *Machine Learning Engineer @ Robinhood*, *Software
Engineer, ML @ Figma*, *AI Engineer @ GitLab*, *AI Research Engineer @ PostHog*,
*Software Engineer, AI Workflows @ Notion*. Scoring: skills 45 / role 30 / location 15
(+ recency/verification). Source mix in the top 100: Ashby 55, Greenhouse 24,
Remotive 13, Arbeitnow 8.

## 6. Feature status (tasks 2–6)

| Task | Status | Notes |
|------|--------|-------|
| 2. Application tracking | ✅ existing | `Application` model + apply/submit/track endpoints |
| 3. Resume-job matching score | ✅ existing | `score_job()`; shown as Match % in Activity Log |
| 4. Duplicate prevention | ✅ verified | `job_url_hash` upsert (2nd track → "Already tracked", 1 row) + aggregator URL/fingerprint dedup |
| 5. Application history dashboard | ✅ existing+extended | `/dashboard/stats` (now includes new stages) + paginated Activity Log |
| 6. Statuses (Applied/Queued/Failed/Interview/Offer) | ✅ added | Interview/Offer/Rejected + Applied are user-settable self-reported stages; Queued now surfaced; Failed already surfaced. Automated outcomes stay evidence-gated (a user still **cannot** fake "Submitted" → 400). |

### Integrity note on "Applied"
Jobora deliberately never lets *automation* emit "Applied" (only evidence-gated
`Submitted`/`Verified Submitted`). "Applied" is now available as a **self-reported**
pipeline stage the user sets by hand in the Activity Log — automation never sets it,
so the no-fabricated-submission guarantee is preserved (verified: 7/7 integrity tests
pass).

## 7. To unlock the disabled sources
- **Workable** — set an authorized account token in env.
- **JSearch** — set a real `JSEARCH_API_KEY` (RapidAPI) and point `JSEARCH_HOST` at the real host.
- **Wellfound** — configure an authorized/licensed feed (no public API).
