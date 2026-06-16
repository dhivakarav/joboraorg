# Greenhouse Flow — Track & Apply on Company Site (High H3)

Closes the last High-priority finding. Greenhouse is now presented honestly: there
is **no in-product auto-submission**, so the UI says **Track & Apply on Company
Site** and clicking Apply opens the official Greenhouse page + records a *Tracked*
event. No label implies a submission occurred. **No Greenhouse pipeline file was
modified** (per the standing constraint) — all changes are UI/flow + wording.

## 1. Misleading "Auto Apply" wording removed (everywhere)
| Location | Before | After |
|---|---|---|
| Find Jobs job card badge | "⚡ Auto-Apply" / "Manual Apply" | **"Apply on company site"** (or "Assisted Apply" for Lever/Ashby) |
| Find Jobs apply button | "Apply" | **"Track & Apply"** (or "Assisted Apply") |
| Find Jobs subtitle | "apply through Jobora" | "track & apply on the company site" |
| Dashboard button | "⚡ Auto-Apply" | **"⚡ Scan & Track Matches"** |
| Dashboard toast/help | "auto-applying to matches" / "hit Auto-Apply" | "tracking matching roles" / "Scan & Track Matches" |
| `ApplyModal.jsx` ("Auto-Apply available.") | present | **file deleted** (orphaned auto-submit modal) |

Final sweep: **0 "auto-apply" strings remain** in active components.

## 2. Greenhouse job presentation
- Badge: **"Apply on company site"** (neutral) + **"✓ Verified listing"** (means
  the *posting* is source-validated — relabeled from "Verified" to avoid confusion
  with "Verified Submitted").
- Button: **"Track & Apply"**.

## 3. Clicking Apply (Greenhouse + all non-assisted sources)
`openApply()` in `FindJobs.jsx`:
1. **Opens the official Greenhouse application page** in a new tab (`apply_url`).
2. **Records a tracked event** → `POST /api/jobs/apply` with `status: "Tracked"`
   (also emits the `tracked_job` analytics event).
3. Card flips to **"✓ Tracked"**; toast: "Opened {company}'s application page —
   tracked in your Activity Log."

Lever/Ashby keep the **Assisted Apply wizard** (captcha-gated, evidence capture).
The old prepare→review→submit modal is gone.

Verified (TestClient): `POST /jobs/apply` (Greenhouse) →
`{status:"Tracked", display_status:"Tracked"}`.

## 4. Dashboard & Activity Log distinguish all four states
Driven by canonical `display_status` (StatusBadge). Verified live:
`by_status = {Draft:0, Tracked:55, Manual Apply:17, Submitted:0, Verified Submitted:0, Failed:0}`.
- **Tracked** — saved/opened, no submission.
- **Manual Apply** — assisted, not yet submitted.
- **Submitted** — a submission was attempted (proof partial).
- **Verified Submitted** — confirmation + application ID + screenshot all on file.

## 5. No status implies submission
Track & Apply writes **Tracked** only. Greenhouse can never reach "Submitted" or
"Verified Submitted" through this flow — those require the evidence-gated paths.
The retired "Applied" label appears nowhere.

## 6. Verification Center = the only source of submission proof
Unchanged and authoritative: only it shows application ID + confirmation URL +
screenshot, and only **Verified Submitted** means all three exist. Track & Apply
rows are not submissions, so they don't claim proof.

## Verification
- Frontend builds clean; `ApplyModal.jsx` removed with no dangling imports.
- 21/21 backend tests pass; no Greenhouse pipeline/matching/integrity code touched.
- Track flow + 4-way status distinction verified via TestClient.

## Outcome
All Critical + High findings from `PRODUCT_COMPLETION_REPORT.md` are now closed
(C1, H1, H2, H3, H4). Every status label is trustworthy: nothing claims a
submission that didn't happen.
