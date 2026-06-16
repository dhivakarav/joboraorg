# Jobara Phase 1 — Platform Readiness Reports

Roadmap rule enforced throughout: **discovery before auto-apply**, and **never
mark "Applied" unless submission is verified**. Auto-apply is enabled **only** for
platforms that passed all six submission-verification gates (form detection,
resume upload, required questions, confirmation detection, application-id
extraction, submission evidence). Today that is **Greenhouse only**.

Shared pipeline (works for any platform once discovery feeds it): internship/
fresher detection (title inference + native type), salary/stipend → INR, dedupe
(stable fingerprint), match scoring, activity tracking (Application + adapter).

Status legend: ✅ done · ⏳ pending-source · ⛔ not enabled (unverified).

| Platform | Discovery | Auto-apply | Apply mode today |
|---|---|---|---|
| Greenhouse | ✅ live (public API) | ✅ **verified (G0–G3)** | Auto-apply |
| Lever | ✅ live (public API) | ✅ **pipeline verified (G0–G3)** — but hCaptcha-gated | Assisted Apply (prefill + human captcha/submit) |
| Ashby | ✅ live (public API) | ✅ **pipeline verified (G0–G3, SPA)** — but reCAPTCHA-gated | Assisted Apply (prefill + human captcha/submit) |
| Workable | ⏳ needs account token | ⛔ unverified | Manual Apply |
| Wellfound | ⏳ needs authorized feed | ⛔ not possible (no API) | Manual Apply |

---

## 1. Greenhouse — READY (discovery + verified auto-apply)
- **Discovery:** ✅ official public board API; provider live.
- **Provider adapter:** ✅
- **Internship / fresher detection:** ✅ (title inference; real intern roles surface)
- **Salary → INR:** ✅
- **Duplicate detection:** ✅ (fingerprint)
- **Match scoring:** ✅
- **Activity tracking:** ✅
- **Auto-apply verification (all six):**
  - Form detection ✅ · Resume upload ✅ · Required questions ✅ · Confirmation
    detection ✅ · Application-id extraction ✅ · Submission evidence ✅
  - Validated end-to-end (G0–G3); status "Verified Submitted" only when
    confirmation + id + screenshot all present.
- **Verdict:** Auto-apply **enabled**. (Before user GA: validate confirmation/id
  on ≥5 real company boards — see B2 report.)

## 2. Lever — discovery READY; submit pipeline VERIFIED; auto-apply hCaptcha-gated
- **Discovery:** ✅ official public postings API; provider live.
- **Provider adapter:** ✅ (manual-only — correctly NOT flipped to auto-submit).
- Internship/fresher detection ✅ · INR ✅ · Dedupe ✅ · Match ✅ · Tracking ✅
- **Auto-apply verification (G0–G3): all six gates PASS at the pipeline level** —
  form detection (Ro + Spotify, 9/9 fields), resume upload, screening questions
  (`cards[<uuid>]`), confirmation detection (`/thanks`), application-id extraction
  (`LVR-…`), evidence capture. See `LEVER_{G1,G2,G3}_REPORT.md`.
- **Key blocker:** every real public Lever form ships an **hCaptcha**, so
  unattended submit is classified `CAPTCHA Required → not Applied`. Lever's public
  API exposes no form spec / submit channel.
- **Verdict:** **Assisted Apply** — Jobora prefills the full form (verified G1/G2),
  the user clears hCaptcha + submits, then G3 confirms + stores evidence. Fully
  unattended auto-apply stays off until an authorized captcha-free channel exists.
  See `LEVER_PRODUCTION_READINESS.md`.

## 3. Ashby — discovery READY; submit pipeline VERIFIED (SPA); auto-apply reCAPTCHA-gated
- **Discovery:** ✅ official public Posting API; provider live. Verified live:
  414 jobs across curated boards; internships detected (Ramp Android Internship,
  Notion Intern); 177 roles with compensation → INR (e.g. `$211.4K–$290.6K →
  ₹1.75 Cr–₹2.41 Cr`).
- **Provider adapter:** ✅ (manual-only — correctly NOT flipped to auto-submit).
- Internship/fresher detection ✅ (native `employmentType` + title inference) ·
  INR ✅ (Ashby compensation field) · Dedupe ✅ · Match ✅ · Tracking ✅
- **Auto-apply verification (G0–G3): all six gates + SPA success handling PASS at
  the pipeline level** — SPA form detection (Ramp + Linear, no `<form>` element),
  resume upload, screening questions (UUID text/textarea **and** Yes/No buttons),
  **DOM-state confirmation** (`url_changed=False`), application-id (`ASH-…`),
  evidence. See `ASHBY_{G1,G2,G3}_REPORT.md`.
- **Key blocker:** every real Ashby form embeds **Google reCAPTCHA**
  (`g-recaptcha-response`), so unattended submit is classified `CAPTCHA Required →
  not Applied`. No public form/submit API.
- **Verdict:** **Assisted Apply** — Jobora prefills the SPA (verified G1/G2), the
  user clears reCAPTCHA + submits, then G3 DOM-state detection confirms + stores
  evidence. Fully unattended auto-apply stays off until an authorized captcha-free
  channel exists. See `ASHBY_PRODUCTION_READINESS.md`.

## 4. Workable — discovery PENDING (authorized token); auto-apply NOT enabled
- **Discovery:** ⏳ Workable has **no free public jobs API** (public endpoints
  return `invalid_token`). The provider activates only with an authorized
  **account token** + subdomains (`WORKABLE_TOKEN`, `WORKABLE_SUBDOMAINS`); until
  then it reports unavailable and returns nothing.
- **Provider adapter:** ✅ (gated; manual-only)
- Pipeline support (internship/fresher, INR, dedupe, match, tracking): ✅ once a
  source is connected.
- **Auto-apply verification:** ⛔ none.
- **Verdict:** **Source pending + Manual Apply.** Connect a Workable account token
  to enable discovery; auto-apply pending G0–G3.

## 5. Wellfound — discovery NOT POSSIBLE (no API + robots); auto-apply NOT enabled
- **Discovery:** ⏳/⛔ Wellfound has **no public API**, and its `robots.txt`
  **disallows** the job paths (`/_jobs/`, `?jobId`, `?jobSlug`, `?role`, `/auth/`).
  Listings sit behind authenticated GraphQL. Jobora does **not** scrape it. The
  provider activates only with an authorized/licensed feed (`WELLFOUND_FEED_URL`);
  otherwise it returns nothing.
- **Provider adapter:** ✅ (gated); **apply adapter is manual-only** (account-gated;
  automation not permitted).
- Pipeline support: ✅ once an authorized feed is connected.
- **Auto-apply verification:** ⛔ not pursued — Wellfound apply is account-gated
  and automation-restricted; **manual apply is the honest end state.**
- **Verdict:** **Source pending + Manual Apply (auto-apply not on the roadmap).**

---

## Summary
- **Discovery live now:** Greenhouse, Lever, **Ashby** (3 of 5).
- **Discovery pending an authorized source:** Workable (account token), Wellfound
  (licensed feed / no public API).
- **Auto-apply verified & enabled:** **Greenhouse only.** Lever and Ashby are
  discovery-ready but **Manual Apply** until their submit pipelines pass the same
  six gates. Workable/Wellfound remain manual.
- **Integrity invariant held:** nothing is marked "Applied" without verified
  submission; no scraping of disallowed sources; no fabricated listings.

## To advance each platform (next steps)
- **Lever / Ashby auto-apply:** run G0 (browser) → G1 (reach real form + detect
  fields) → G2 (fill + resume + required questions) → G3 (submit + confirmation +
  app-id + evidence) against real forms; only then flip `supports_auto_submit`.
- **Workable discovery:** provide `WORKABLE_TOKEN` + `WORKABLE_SUBDOMAINS`.
- **Wellfound discovery:** secure a licensed/partner feed → `WELLFOUND_FEED_URL`.
