# Evidence Column — Behavior Audit (read-only)

_Date: 2026-06-12. No code modified. Traced `ActivityLog.jsx`, `EvidenceModal.jsx`,
the `/applications/{id}/evidence` endpoint, and the live DB._

## The cell logic (Activity Log → "Evidence" column)
```jsx
{["Verified Submitted","Submitted","Failed","CAPTCHA Required","Manual Apply Required"]
   .includes(r.submission_status)
  ? <button onClick={() => setEvidenceApp(r)}>View</button>   // opens Evidence modal
  : r.apply_url
    ? <a href={r.apply_url} target="_blank">Open ↗</a>         // opens the apply URL
    : "—"}
```
**Key fact:** the decision is made on the **raw `submission_status`**, against a
**legacy value list**, not on the canonical `display_status` the rest of the row uses.

## Exact URL opened, per status
| Status (display) | Stored `submission_status` | Cell shows | Click opens |
|---|---|---|---|
| **1. Tracked** | `Draft` | **Open ↗** | **`apply_url`** — the real company job/application page |
| **2. Manual Apply** | `Manual Apply` (or `Draft` for career-page manual) | **Open ↗** | **`apply_url`** — the company application page |
| **3. Submitted** | `Submitted` | **View** (modal, *not* "Open") | Evidence modal → `GET /api/applications/{id}/evidence`; inside, "Confirmation URL → Open ↗" opens **`confirmation_url`**, and the screenshot opens a **short-lived signed URL** (`/api/applications/{id}/evidence/screenshot?token=…` or an S3 presigned URL) |
| **4. Verified Submitted** | `Verified Submitted` | **View** (modal) | Same as Submitted: Evidence modal → `confirmation_url` + signed screenshot URL + application ID |

**Live DB confirms (no real submissions yet):** 84 `Tracked/Draft` and 31
`Manual Apply` rows — **all** currently resolve to **Open ↗ → `apply_url`**. No
`Submitted`/`Verified Submitted` rows exist to exercise the "View" branch in the
running data, but the code path above is what they would hit.

## Does this match the intended design?
**Partially. Submitted / Verified Submitted are correct; Tracked / Manual Apply are
a semantic deviation; and the cell uses a stale, inconsistent condition.**

### ✅ Correct
- **Submitted → View → Evidence modal** (confirmation URL + signed screenshot): matches
  intent — proof of submission, served via a short-lived signed URL (owner-scoped).
- **Verified Submitted → View → Evidence modal** with ID + confirmation + screenshot:
  matches intent.

### ⚠️ Deviations / issues
1. **Tracked → opens the apply page, not evidence.** A *Tracked* job has no evidence,
   yet the "Evidence" column shows **Open ↗** and navigates to the **company apply
   page** (`apply_url`). This is a convenience link, but it conflates "evidence" with
   "go apply." If the intended design is *"Evidence = proof for submissions, else
   —,"* this is off-spec.
2. **Manual Apply → opens the apply page via a *fall-through bug*.** The View-list
   checks the **legacy** value `"Manual Apply Required"`, but the canonical stored
   value is **`"Manual Apply"`** (or `Draft`). Neither matches, so Manual Apply rows
   land in the `apply_url` branch. It's *currently harmless* (Manual Apply rows have
   no evidence anyway), but it's **relying on a stale condition list**, not intent.
3. **Cell keys off `submission_status`, not `display_status`.** The Status badge uses
   the canonical `display_status`; the Evidence cell uses raw `submission_status`
   against legacy values (`"Manual Apply Required"`, `"CAPTCHA Required"`). These can
   **diverge** — e.g. a row stored as `submission_status="Verified Submitted"` but
   missing evidence is **display-downgraded to "Submitted"**, yet the Evidence cell
   still matches the raw `"Verified Submitted"` and shows **View** (the modal would
   then show "no screenshot"). Inconsistent source of truth.
4. **Inconsistent with the Verification Center.** That page's Evidence cell uses a
   different rule — `r.evidence_available || r.confirmation_url ? View : "—"` (keyed
   on *actual evidence presence*). The two pages disagree on when to show "View".

## Summary
- **What opens:** Tracked & Manual Apply → **`apply_url`** (Open ↗); Submitted &
  Verified Submitted → **Evidence modal** (→ `confirmation_url` + signed screenshot
  URL).
- **Intended-design match:** ✅ for Submitted/Verified; ⚠️ for Tracked/Manual Apply,
  which open the apply page rather than showing/omitting evidence, driven by a
  **stale `submission_status` condition** that should be the canonical `display_status`
  (or `evidence_available`) for consistency with the Status badge and the Verification
  Center.

_No changes made. Recommended fix (when authorized): key the cell on `display_status`
/ `evidence_available`, show "View" only for `Submitted`/`Verified Submitted`, and use
"Open ↗" or "—" otherwise — matching the Verification Center._
