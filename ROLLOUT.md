# Jobara — Auto-Apply Platform Rollout Plan

One platform reaches production before the next begins. **Greenhouse is the
reference implementation**; the others follow the same G0→G3→Production gates.

## Non-negotiable invariants (every platform)
1. Submit only on the **user's explicit click**, with their **real resume** and a
   **complete profile**.
2. **Never fabricate** answers. A required screening question with no
   user-provided answer → **Manual Apply Required** (no auto-fill).
3. **"Verified Submitted"** requires all three: confirmation page detected +
   application id extracted + screenshot stored. Otherwise Submitted/Failed/CAPTCHA.
4. CAPTCHA / validation / rejection → record **failure with evidence**, never a
   false success.
5. Live submission is gated behind `JOBORA_LIVE` + an installed browser; if not
   ready → Manual Apply Required.

## Per-platform gate checklist (the "definition of done")
- **G0** Playwright + safe live-mode guard
- **G1** Reach the real form (resolve URL, iframe-aware) + detect all fields
- **G2** Fill all field types (text, dropdown, radio, checkbox) + resume upload + required-field validation + screenshots
- **G3** Submit + confirmation detection + application-id extraction + evidence (controlled fixture first)
- **PROD** Wire to real users, DB persistence, statuses, evidence page, Activity Log

---

## 1. Greenhouse — ✅ Production Phase 1 (reference)
- Status: G0–G3 done; production endpoint `POST /api/jobs/greenhouse/apply` live, gated, evidence-backed.
- Form: `boards.greenhouse.io/embed/job_app?token={id}`; fields from the Board API (`?questions=true`).
- Remaining hardening before GA: validate confirmation/ID regexes against several **real** company confirmations; handle reCAPTCHA postings (→ Manual); "paste resume text" mode; rate-limit per user/day; S3 evidence storage for multi-replica.

## 2. Lever — next
- Discovery API already integrated. Apply form: `jobs.lever.co/{company}/{id}/apply`.
- Fields: name, email, resume (`input[name=resume]`), `urls[LinkedIn]`, custom cards.
- Confirmation: "Thank you for applying" page. Effort: **Low–Medium** (simpler DOM than Greenhouse, mostly text inputs; fewer custom widgets).
- Work: G1 selectors → G2 fill (Lever uses native inputs + some custom selects) → G3 confirmation/ID → reuse the production endpoint pattern.

## 3. Ashby — after Lever
- Apply form: `jobs.ashbyhq.com/{org}/{id}/application`. Heavy React SPA.
- Fields via `aria-label`; file upload widget; custom dropdowns.
- Confirmation: in-app success state (no full navigation) — needs success-element detection, not just URL change.
- Effort: **Medium–High** (SPA state, dynamic rendering). Extra G1 work to wait for hydration.

## 4. Internshala — India-focused
- **Requires login** (account-gated apply) and is India-specific. No public board API.
- Apply flow: cover-letter + assessment questions, often mandatory.
- Effort: **High** + **ToS/login risk** — needs the user's own authenticated session; likely **assisted/Manual-first** rather than full auto-submit. Treat as Manual Apply with prefill until a compliant path exists.
- Discovery: would need a separate integration (no Greenhouse/Lever-style API).

## 5. Workable — last of this set
- Apply form: `apply.workable.com/{company}/j/{id}/`. React SPA, multi-step.
- File upload + parsed-resume autofill + custom questions; sometimes multi-page.
- Confirmation: success screen. Effort: **Medium–High** (multi-step flow, step navigation in G2/G3).

---

## Sequencing & exit criteria
```
Greenhouse (prod-harden) → Lever → Ashby → Workable → Internshala(assisted)
```
A platform is "production" only when, on ≥5 real postings: form reached,
required fields filled from genuine data, submit → confirmation detected → ID
extracted → evidence stored, and CAPTCHA/validation correctly downgrade to
failure/manual. Until then it stays **Manual Apply Required** in the UI — honest
by default.

## Cross-cutting work (parallel, platform-agnostic)
- Per-user/day submission rate limiting (Redis).
- Evidence storage → S3 (currently local `uploads/evidence/`).
- A pre-submit review screen that collects answers to required screening
  questions (so auto-submit fires more often without fabrication).
- Audit log + admin visibility into submission outcomes.
- Retry/backoff and anti-bot handling per platform.
