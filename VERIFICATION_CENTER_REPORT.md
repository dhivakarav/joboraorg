# Verification Center — Report (High H4)

A dedicated page for proof of every submission, replacing the modal-only access.
No integrity logic changed — it reuses the existing canonical status + evidence APIs.

## Location
- Page: `frontend/src/pages/user/VerificationCenter.jsx`
- Route: `/app/verification` · Nav: **"✓ Verification Center"** (Layout sidebar)
- Data: `GET /api/applications` (list) + `GET /api/applications/{id}/evidence`
  (short-lived signed screenshot URL, via the existing `EvidenceModal`).

## What it shows (per submission)
| Column | Source |
|---|---|
| Role + Company | application |
| **Portal** | `platform` (Greenhouse / Lever / Ashby / …) |
| **Verification status** | canonical `display_status` badge |
| **Application ID** | `application_id` / `external_application_id` |
| **Confirmation URL** | `confirmation_url` (opens in new tab) |
| **Submission timestamp** | `submitted_at` |
| **Screenshot evidence** | "View" → `EvidenceModal` (signed URL) |

Top summary cards: **Verified Submitted**, Submission attempts, Tracked
(not submitted), Total applications. A **"Show only Verified Submitted"** toggle
filters to fully-evidenced rows.

## Scope of rows
Shows submission **attempts** only — `display_status` in
{Verified Submitted, Submitted, Manual Apply, Failed}. Pure `Tracked`/`Draft`
rows are excluded (they're not submissions) but counted in the summary.

## Integrity (unchanged, enforced upstream)
- **Verified Submitted** appears only when confirmation + application ID +
  screenshot all exist (gated in `app/status.py` + record endpoint).
- No "Applied" anywhere; nothing fabricated. The page is read-only over real data.

## Verification
- Frontend builds clean; route + nav wired; reuses the audited evidence endpoint.
- Empty state guides users to apply from Find Jobs (assisted applies populate it).
