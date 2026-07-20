# Publishing the Jobora extensions to the Chrome Web Store

Two separate extensions ship separately (own listing, own "Add to Chrome" link):

| Extension | Package to upload |
|---|---|
| Jobora — LinkedIn Copilot | `extensions/dist-packages/jobora-linkedin-extension.zip` |
| Jobora — Internshala Copilot | `extensions/dist-packages/jobora-internshala-extension.zip` |

Both are built against the **production** API (`https://jobara-api.onrender.com/api`),
have icons (16/32/48/128), and carry no `localhost`/unused host permissions.

---

## ⚠️ Prerequisite — the backend MUST be current first

The extensions call new endpoints (`/jobs/answer-field`, honest scoring, Internshala
scoring). **Production `jobara-api.onrender.com` is currently stale.** Before users
install, redeploy the backend and set env vars:

1. Render Dashboard → `jobara-api` → **Manual Deploy → Deploy latest commit** (from `main`).
2. Ensure these env vars are set on `jobara-api`:
   - `GROQ_API_KEY` (required for AI answers / cover letters)
   - `JOBORA_ENV=production`, plus your existing DB/Redis/secret vars.
3. Verify: `curl https://jobara-api.onrender.com/openapi.json | grep answer-field` → present.
4. (Recommended) Upgrade `jobara-api` from **free → starter** so it doesn't cold-start (30s).

Until this is done, the extensions install but AI features return empty.

---

## One-time setup
1. Create a Chrome Web Store developer account: https://chrome.google.com/webstore/devconsole (US$5 one-time).
2. Have a privacy-policy URL ready: **https://jobora.app/privacy** (already live; source in `legal/PRIVACY_POLICY.md`).

## For EACH extension
1. Dev console → **Add new item** → upload the `.zip`.
2. Fill the listing (content below).
3. **Privacy practices** tab → add the single-purpose description + permission justifications (below).
4. Submit for review (typically 1–3 days).
5. After it's **published**, copy the store URL and paste it into
   `frontend/src/pages/Extensions.jsx` → `STORE_URLS.linkedin` / `.internshala`,
   then redeploy the frontend. The "Add to Chrome" buttons go live.

---

## Listing content

### Jobora — LinkedIn Copilot
- **Category:** Productivity
- **Summary (≤132 chars):** Honest resume-match scoring and bulk auto-apply for LinkedIn — apply only to jobs you actually fit.
- **Description:**
  > Jobora is your honest job-application copilot for LinkedIn. It scores every job
  > against your resume (and tells you which to skip), then bulk auto-applies to the
  > good ones via LinkedIn Easy Apply — filling contact info, resume, and screening
  > questions from your resume with AI. A built-in safety meter stops at a safe daily
  > limit to protect your account. It never fabricates experience: if a question needs
  > an answer your resume can't support, it pauses and asks you. Requires a free Jobora
  > account (jobora.app).

### Jobora — Internshala Copilot
- **Category:** Productivity
- **Summary (≤132 chars):** Auto-apply to eligible Internshala internships with honest resume-match scoring and AI cover letters.
- **Description:**
  > Jobora's Internshala copilot scores every internship against your resume and
  > auto-applies to eligible, matching ones — walking Apply → Proceed → cover letter →
  > Submit for you, with AI-written answers grounded in your resume. It skips roles
  > you're not eligible for, stops at a safe daily limit, and sounds a loud alert if a
  > form genuinely needs your input. Requires a free Jobora account (jobora.app).

---

## Privacy practices (required to pass review)

**Single purpose:** Help the signed-in user find and apply to jobs/internships that
match their resume, by scoring listings and auto-filling application forms.

**Permission justifications:**
- `storage` — save the user's Jobora login token and autofill preferences locally.
- `alarms` — periodically refresh the login token so the session stays valid.
- `notifications` — tell the user when auto-apply needs their input or hits the daily limit.
- **Host permissions** (`linkedin.com` / `internshala.com`, etc.) — read the job listing
  on the page the user is viewing to score it, and fill the application form on that page.
- `jobara-api.onrender.com`, `*.jobora.app` — the user's own Jobora backend (scoring,
  resume, AI answers).

**Data use disclosures (tick honestly):** collects "Personally identifiable information"
(name/email/phone used to fill applications) and "Web history" is NOT collected. Data is
sent only to the user's Jobora backend to score jobs and prepare applications. Not sold,
not used for advertising. Privacy policy: https://jobora.app/privacy

**Remote code:** No (all JS is bundled in the package).
