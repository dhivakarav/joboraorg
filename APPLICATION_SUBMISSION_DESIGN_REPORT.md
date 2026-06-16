# Application Submission — Design Audit

_Date: 2026-06-12. Read-only design report; no code modified. Grounded in the
current adapters, G0–G3 pipelines, and `load_profile`._

## Capability matrix (as implemented)
| Platform | Apply mode today | `auto_submit` | Submission mechanism | Captcha on public form | App ID exposed? |
|---|---|---|---|---|---|
| **Greenhouse** | Track & Apply (default) **+** gated auto-submit | `True` | **Browser automation** (Playwright); no candidate API | Risk-based (often none) | **Rarely** (`GH-…` extracted if shown) |
| **Lever** | Assisted Apply | `False` (`manual_only`) | Browser automation for **prefill only**; user submits | **hCaptcha (always)** | **Rarely** (`LVR-…` if shown) |
| **Ashby** | Assisted Apply | `False` (`manual_only`) | Browser automation (SPA) for prefill; user submits | **reCAPTCHA (always)** | **Rarely** (`ASH-…` if shown) |
| **Generic career page** | Track & Apply | `False` (`manual_only`) | None — user applies on site | Varies | No |

---

## 1. Which providers support programmatic application submission?
**Strictly, none expose a candidate-submission API.** All ATS "APIs" here are
*read-only job-board APIs* (discovery), not apply APIs.
- **Greenhouse — the only one with an automated submit path**, and it is
  **browser-driven** (the verified G0–G3 pipeline fills + submits the real embedded
  form headlessly). It is gated by `JOBORA_LIVE=1` **and** per-application approval
  **and** a real uploaded resume; with live mode off it degrades to "prepared".
- **Lever / Ashby — no programmatic submit.** Their public forms always ship a
  captcha, so unattended completion is impossible by design.
- **Generic — no programmatic submit.** No consistent form to drive.

## 2. Which providers require browser automation?
**All submission flows require browser automation — there is no REST submit
anywhere.** The difference is whether automation can *complete*:
- **Greenhouse:** automation can complete end-to-end **when no captcha appears**
  (Playwright drives fill → submit → confirmation). A captcha aborts → recorded as
  "CAPTCHA Required", never a false success.
- **Lever / Ashby:** automation is used to **prefill** (and was used to verify the
  pipeline G0–G3), but the **final submit is the user's browser** — they clear the
  hCaptcha/reCAPTCHA and submit. Automation cannot finish.
- **Generic:** no automation; fully manual on the company site.

## 3. Which providers expose an application ID after submission?
**None reliably.** Real employer confirmations usually show a "thank you" with **no
public reference id**:
- Greenhouse — sometimes a confirmation number; the pipeline extracts `GH-[A-Z0-9]{6,}`
  if present, else records **"Submitted"** (no id).
- Lever — `LVR-…` extracted if present; real Lever `/thanks` typically has none.
- Ashby — `ASH-…` extracted if present; real Ashby shows an **in-app** success panel
  (no URL change), usually no id.
- Generic — none.

Consequence: the honest **"Verified Submitted"** status (which requires
**application id + confirmation URL + screenshot**) is **frequently unreachable** on
real submissions; many genuine submissions correctly land as **"Submitted"**.

## 4. Fields required to submit automatically from the stored resume/profile
**Stored & auto-fillable** (`load_profile`): `name`, `email`, `phone`, `location`,
`linkedin_url`, `portfolio_url`, `skills`, `experience`, `seeker_type`, `resume_path`
(the encrypted resume, materialized to a temp PDF for upload).

| Field | Greenhouse | Lever | Ashby | Source |
|---|---|---|---|---|
| First / Last name | ✅ required (must **split** our single `name`) | `name` (single) | `_systemfield_name` | profile |
| Email | ✅ | ✅ | ✅ | profile |
| Phone | ✅ | ✅ | `input[type=tel]` | profile |
| Resume file | ✅ | ✅ | `_systemfield_resume` | profile (decrypt→upload) |
| LinkedIn / Portfolio / GitHub | optional | `urls[…]` | optional | profile (no GitHub stored) |
| **Current employer / `org` + title** | required (some) | **`org` required** | — | ❌ **not stored** |
| **Work authorization / visa sponsorship** | ✅ required | required (cards) | required | ❌ **must be user-answered** |
| **"Why this role" essay / availability** | ✅ required | required (cards) | required (UUID Qs) | ❌ **must be user-answered** |
| **GPA / grad date / PhD advisor** (some) | — | — | required (Ashby Qs) | ❌ user-answered |
| EEO / demographics | optional | optional | optional | not collected |
| **Captcha** | risk-based | **hCaptcha** | **reCAPTCHA** | **human-only** |

**Gap:** the profile covers identity + resume + URLs, but **required screening
questions** (work auth, visa, essays, availability, current employer/title, GPA) and
the **captcha** are **not** auto-fillable. Auto-answering them would be **fabrication**
under the user's name — forbidden by the integrity model — so fully-unattended
submission is impossible for Lever/Ashby and unsafe-to-claim for Greenhouse without
the user's real answers. (Even Greenhouse auto-submit needs the user to supply
screening answers + approve.)

## 5. Risks

### Legal / compliance
- **ToS:** automating submissions on public ATS forms may breach the ATS or
  employer terms (forms are for human applicants); some explicitly prohibit bots.
- **Captcha circumvention:** hCaptcha/reCAPTCHA exist to block automation; bypassing
  them (e.g. solver services) is a ToS violation and ethically/legally fraught — we
  deliberately do **not**.
- **Misrepresentation:** auto-filling screening answers under the user's name without
  their input misleads employers and harms the user.
- **Consent & irreversibility:** submitting is an outward-facing, irreversible action
  with the user's PII/resume — it needs explicit, informed, **per-application**
  consent.
- **Computer-misuse exposure:** automated access contrary to terms can carry
  jurisdiction-specific risk.

### Technical
- **No submit APIs** → must drive real DOM forms via Playwright: brittle (selectors
  drift), slow, resource-heavy (headless Chromium), and needs the resume decrypted to
  a temp file.
- **Captcha** is a hard blocker (Lever/Ashby) and a risk-based blocker (Greenhouse).
- **Heterogeneous confirmation detection** (Greenhouse redirect/markers, Lever
  `/thanks`, Ashby in-app DOM-state) → bespoke per platform; false-success risk.
- **App IDs rarely exposed** → "Verified Submitted" hard to reach honestly.
- **Dynamic required questions** (UUID `cards[]`, posting-specific) can't be
  pre-mapped from a static profile.

### Maintenance
- **ATS form/selector churn** → ongoing upkeep of fill/submit/confirmation logic.
- **Captcha & anti-bot evolution** → detection must keep pace.
- **Per-employer variation** (boards, custom questions) → long-tail maintenance.
- **Browser infra** (Playwright/Chromium versions, headless detection, IP reputation,
  rate limits) → operational burden + block risk.
- **Evidence plumbing** (storage, signed URLs, retries, idempotency, dedupe).

---

## Design assessment & recommendation (no change proposed here)
The current architecture already reflects the honest constraints:
- **Greenhouse → Track & Apply** by default; the verified automated pipeline exists
  but stays **gated** (`JOBORA_LIVE` + approval + user-provided screening answers),
  and only marks **Verified Submitted** with full evidence.
- **Lever / Ashby → Assisted Apply** (prefill what we own; the user clears the
  captcha + submits; we record evidence).
- **Generic → Track & Apply.**

**Do not pursue fully-unattended auto-submit for captcha-gated platforms** — it is
blocked legally (ToS/captcha) and technically (captcha + required human answers).
The only path to *true* programmatic submission is an **authorized ATS partner/Apply
API** (a business agreement) — which none of these offer publicly for candidates.

**If submission scope is ever expanded**, the safe, integrity-preserving increments
would be (in order): (a) capture & store the user's reusable answers (work auth,
visa, current employer/title, a short "why" blurb) and add `first/last` + `org` to
the profile so prefill is more complete; (b) keep the human in the loop for captcha
+ final submit (Assisted Apply); (c) only auto-complete Greenhouse when no captcha
is present, with explicit per-application approval and real screening answers — never
fabricated.

_No code was modified. This is design analysis only._
