# Product Completion Report — Jobora

_Date 2026-06-11. Live in-process verification (FastAPI TestClient + real
providers) + code review. Payments removed from the active product (billing
router unregistered → `/api/billing/*` returns 404). No new job boards. No
matching/integrity changes._

## Flow verification (12 flows)
| Flow | Result | Evidence |
|---|---|---|
| Signup / Login | ✅ Works | `/auth/register` (invite gate), `/auth/login` 200, `/auth/me` present, admin-approval + email-verify in place |
| Resume Upload | ✅ Works | `/resume/upload` (PDF, encrypted at rest) |
| Resume Parsing | ⚠️ Works, accuracy varies | pdfplumber heuristics; `/resume/parsed` 200; edit endpoint exists |
| Job Search | ⚠️ Works but slow + sparse | `/jobs` 200 — **cold fetch ~8.5s** across ~10 live providers; "software intern" → **0 results** after strict filter |
| Matching + Eligibility | ✅ Works | tiers, `early_signal`, "Why matched?" reasons returned; student-first ranking |
| Greenhouse Apply | ⚠️ Pipeline verified, not user-runnable | G0–G3 verified; live OFF (`JOBORA_LIVE=0`); no in-product submit path |
| Lever Assisted Apply | ⚠️ Backend only | `/jobs/assisted/prepare` + `/record` exist; **no frontend wizard**; 400 here = resume-gate cascade |
| Ashby Assisted Apply | ⚠️ Backend only | same as Lever; SPA DOM-state confirmation verified |
| Activity Tracking | ✅ Works | `/applications` 200; canonical statuses; **0 "Applied" leaks** |
| Verification Center | ⚠️ Partial | evidence endpoint 200, but **no dedicated page** — only a modal from Activity Log |
| Settings | ✅ Works | `/profile/update` + `/profile/password` + `/auth/me` |
| Dashboard | ✅ Works | `/dashboard/stats` 200; canonical, evidence-honest counts |

---

## Findings (classified)

### 🔴 Critical
- **C1 — Assisted Apply has no front-end.** Lever/Ashby `prepare`/`record`
  endpoints work, but there is **no UI** to drive prefill → review → record
  evidence. The platform's headline "assisted apply" flow is **not usable
  in-product** today.

### 🟠 High
- **H1 — Cold job search is slow (~8.5s).** First search fans out to ~10 live
  providers synchronously-per-request (cached for 15 min after). Risk of perceived
  hang on first use.
- **H2 — Empty results on common student queries.** With the strict
  internships-&-new-grad filter on the current providers, "software intern"
  returned **0 results** (9 hidden ineligible + 6 generic filtered). The primary
  flow frequently shows nothing.
- **H3 — No in-product Greenhouse submission.** The verified pipeline is gated
  (`JOBORA_LIVE=0`, needs approval + truthful answers); users currently can only
  **track** Greenhouse roles, not submit through Jobora.
- **H4 — No Verification Center page.** Evidence is reachable only as a modal;
  there's no standalone "my verified submissions + proofs" screen.

### 🟡 Medium
- **M1 — Vestigial "Job Portals" feature.** Nav hidden, but the route, page, and
  `PortalCredential` model remain; `dashboard/stats.active_portals` still
  references it. Dead/confusing.
- **M2 — Not mobile-responsive.** Fixed `w-64` sidebar, no hamburger/drawer; on
  phones the layout is cramped.
- **M3 — Thin test coverage for new code.** 21 tests pass but eligibility,
  assisted-apply, feedback, and analytics have no automated tests.
- **M4 — Resume parsing accuracy + correction UX.** Heuristic parsing misses
  fields on varied layouts; correction flow is minimal.

### 🟢 Low
- **L1 — Dev ephemeral `CREDENTIAL_KEY`** makes resumes undecryptable across
  restarts (prod requires a stable key; app now degrades gracefully).
- **L2 — `billing.py` parked dead code** (router unregistered; file remains).
- **L3 — `EXPOSE_RESET_TOKEN` must be `0` in prod** (defaults to dev-friendly 1).
- **L4 — Minor empty/loading states** missing on Resume/Settings.

### Security (reviewed — strong)
Fail-closed secrets, JWT access+refresh+revocation, bcrypt, Redis rate limiting,
PII/credential encryption, short-lived evidence URLs, admin approval, CORS allow-
list. **No critical/high security issues.** Only L3 above.

### Performance
Dashboard/applications < 15 ms. **Cold job search ~8.5 s** (H1) is the one hot
spot; warm (cached) searches are fast.

---

## Prioritized implementation roadmap

### Sprint 1 — Make the core promise real (Critical/High)
1. **C1 — Build the Assisted-Apply wizard** (Lever + Ashby): a guided modal/page
   that calls `/prepare`, shows prefill + the apply URL + "complete captcha &
   submit", then a "record confirmation (URL + id + screenshot)" step calling
   `/record`. This unlocks the headline flow.
2. **H4 — Verification Center page**: list the user's submissions with
   display_status + evidence (reuse the evidence endpoint); promote it in nav.
3. **H2 — Fix empty results UX**: when the internship filter yields few/zero,
   auto-suggest "show all eligible" + clearly explain scarcity; keep results > 0
   whenever any eligible role exists.
4. **H1 — Search performance**: warm/refresh cache in the background, show
   per-provider progressive results or a skeleton, and shorten provider timeouts.

### Sprint 2 — Honesty + polish (High/Medium)
5. **H3 — Greenhouse apply decision**: either expose an approval-gated live submit
   (with truthful-answer capture) or relabel Greenhouse as "Track + apply on site"
   so the UI doesn't over-promise.
6. **M2 — Mobile responsive layout** (collapsible sidebar / bottom nav).
7. **M1 — Remove the vestigial Portals feature** (route + page + model + the
   `active_portals` stat) or repurpose.

### Sprint 3 — Hardening (Medium/Low)
8. **M3 — Tests** for eligibility, assisted-apply, feedback, analytics.
9. **M4 — Resume parsing** improvements + a clear correction screen.
10. **L2/L3/L4** cleanup (remove parked billing, prod env defaults, empty states).

## Completion estimate
- **Verified-working core** (auth, resume, search, matching, tracking, dashboard,
  settings, evidence): **~90%**.
- **End-to-end apply experience** (assisted UI + verification center): **~45%**
  (backend done, UI missing).
- **Overall product completeness: ~75%.** Closing **C1 + H1–H4 (Sprint 1)** takes
  it to a genuinely complete student job-application platform.
