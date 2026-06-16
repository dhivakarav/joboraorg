# Jobora — User Guide

Jobora helps students and early-career job seekers **find real openings, see which
ones fit, and track applications honestly** — it never claims you applied to
something unless there's proof.

## Getting started
1. **Register** at `/register` (full name, email, password; optional phone, years
   of experience, job title). If beta invites are enabled, you'll need an invite
   code.
2. Your account starts **pending admin approval**. You'll land on a "pending"
   screen until an admin approves you (and, if email verification is on, after you
   verify your email).
3. Once approved, **log in** at `/login`. You'll see a one-time **"How Jobora
   works"** walkthrough on the Dashboard.
4. **Set your stage** (Student / Fresher / Experienced) in onboarding or Settings —
   this drives how strictly results are filtered.

## The pages (left sidebar)
| Page | What it does |
|---|---|
| **Dashboard** | Overview: Verified Submitted / Submitted / Manual Apply / Tracked counts, recent activity, and a "Scan & Track Matches" action. |
| **Find Jobs** | Discover real jobs matched to your resume. |
| **Resume** | Upload your resume; review/correct parsed fields. |
| **Filters** | Set preferred roles, locations, keywords. |
| **Activity Log** | Every job you've tracked/applied to, with its status. |
| **Verification Center** | Proof of every submission (ID, confirmation URL, screenshot). |
| **Settings** | Job stage, profile, password. |

## 1. Upload your resume (do this first)
Go to **Resume → Upload**. Jobora parses your name, email, location, **skills**, and
**education** from the PDF. Anything parsed incorrectly is **editable** on the same
page — fix it before searching, since matching uses these fields. Your resume is
**encrypted at rest**.

## 2. Find Jobs
Open **Find Jobs**. Results are **ranked for early-career fit**, not just keywords:
- **Eligibility tier** badge — ★ **Excellent Match** · **Good Match** · Possible ·
  Not Recommended. Senior / staff / principal / manager / PhD-only / "3+ years" /
  visa-restricted roles are hidden by default.
- **Type badge** — Internship · New Grad · Fresher Friendly.
- **"Why matched?"** panel — the reasons a role was surfaced.
- **Internships & New Grad only** toggle (above results) — ON by default for
  students/freshers; it shows only roles with an explicit intern/new-grad/fresher
  signal. Turn it off ("what's this?" explains it) to see all eligible roles.
- If a search is empty, the page explains **why** (e.g. "12 generic + 9 senior roles
  hidden") and offers **Show all eligible** / **Browse all**.
- **Search box + location**, and a **Refresh** to bypass the cache.
- The **Sources** row shows which providers are active (●) vs. pending a key (○).

## 3. Apply — two honest paths
Jobora **does not** auto-submit applications for you. Depending on the source:

- **Track & Apply on Company Site** (Greenhouse and most sources): clicking **Track
  & Apply** opens the **official application page** in a new tab and records the job
  as **Tracked** in your Activity Log. You complete the application on the company's
  site.
- **Assisted Apply** (Lever / Ashby): clicking **Assisted Apply** opens a wizard:
  1. **Review** — your profile details (name/email/phone/resume + LinkedIn/portfolio)
     prefilled, the required fields, and a note that you must answer any screening
     questions truthfully on the portal.
  2. **Apply** — open the real page, complete the **captcha**, and submit.
  3. **Record** — paste your **confirmation URL + reference/application ID** and
     upload a **screenshot** of the confirmation.

## 4. Application statuses (what they mean)
| Status | Meaning |
|---|---|
| **Draft** | Saved only. |
| **Tracked** | You're following / opened it on the company site. **Not** submitted. |
| **Manual Apply** | An assisted apply was started; not yet submitted. |
| **Submitted** | A submission was attempted (partial proof). |
| **Verified Submitted** | Confirmation + application ID + screenshot all on file. |
| **Failed** | A submission attempt failed. |

**Jobora never shows "Applied".** A role only reads **Verified Submitted** when all
three proofs exist — so your tracker reflects reality.

## 5. Verification Center
Shows every submission attempt with its **portal, status, application ID,
confirmation URL, screenshot, and timestamp**. Filter to "only Verified Submitted"
to see fully-evidenced applications.

## 6. Feedback & bugs
A floating **💬 Feedback** button on every page lets you send feedback or report a
bug (with severity). The team reads every beta report.

## Tips
- Keep your **resume + Filters** accurate — matching and eligibility depend on them.
- If results are sparse, **turn off "Internships & New Grad only"** — internship
  postings are bursty.
- "Scan & Track Matches" (Dashboard) scans your profile and tracks matching roles;
  it **does not** auto-submit anything.
