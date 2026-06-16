# Evidence Column Fix — Implementation Report

_Date: 2026-06-12. Implements the recommendation from `EVIDENCE_COLUMN_AUDIT.md`.
**Frontend only — all backend APIs unchanged.**_

## What was wrong (from the audit)
The Activity Log "Evidence" cell decided on the **raw `submission_status`** against a
**stale legacy list** (`"Manual Apply Required"`, `"CAPTCHA Required"`), diverging
from the canonical `display_status` used everywhere else, and was inconsistent with
the Verification Center's cell.

## The fix
A single canonical **`EvidenceCell`** component (in `components/UI.jsx`), now used by
**both** the Activity Log and the Verification Center (one source of truth):

```jsx
export function EvidenceCell({ row, onView }) {
  const ds = row.display_status;
  const hasEvidence = !!row.evidence_available || !!row.confirmation_url;
  if ((ds === "Submitted" || ds === "Verified Submitted") && hasEvidence)
    return <button onClick={() => onView(row)}>View</button>;   // → Evidence modal
  if ((ds === "Tracked" || ds === "Manual Apply") && row.apply_url)
    return <a href={row.apply_url} target="_blank" rel="noopener noreferrer">Open ↗</a>; // → apply page
  return <span>—</span>;
}
```

### Rules implemented (exactly as requested)
| Condition | Cell | Action |
|---|---|---|
| `display_status` ∈ {Submitted, Verified Submitted} **and** has evidence (`evidence_available` or `confirmation_url`) | **View** | opens the Evidence modal (confirmation URL + short-lived signed screenshot) |
| `display_status` ∈ {Tracked, Manual Apply} **and** `apply_url` present | **Open ↗** | opens the company apply page (`apply_url`) |
| anything else, or no evidence | **—** | nothing to show |

### Behavior per status (after fix)
| Status | Before | After |
|---|---|---|
| **Tracked** | Open ↗ (apply_url) | **Open ↗ (apply_url)** ✅ |
| **Manual Apply** | Open ↗ (via stale fall-through) | **Open ↗ (apply_url)** ✅ now via canonical `display_status` |
| **Submitted** (with evidence) | View | **View** ✅ |
| **Submitted** (no evidence) | View (empty modal) | **—** ✅ no misleading "View" |
| **Verified Submitted** | View | **View** ✅ |
| **Failed / Draft / other** | Failed→View | **—** (per the new spec: View is only for Submitted/Verified) |

> Note: per the requested rules, **Failed** rows now show **"—"** in this column
> (previously "View"). This is a deliberate narrowing — the Evidence column is now
> strictly for *submission proof*. (Submission status remains visible via the Status
> badge / submission detail.)

## Files changed (frontend only)
- `components/UI.jsx` — added the shared `EvidenceCell`.
- `pages/user/ActivityLog.jsx` — replaced the inline `submission_status` ternary with
  `<EvidenceCell row={r} onView={setEvidenceApp} />`; imported `EvidenceCell`.
- `pages/user/VerificationCenter.jsx` — replaced its ad-hoc cell with the same
  `EvidenceCell` (now identical logic → audit's AL↔VC inconsistency resolved).

**No backend changes.** `ApplicationOut` already exposes `display_status`,
`evidence_available`, `confirmation_url`, and `apply_url` — no API was modified.

## Consistency & integrity
- Both pages now use **one** canonical rule keyed on `display_status` +
  evidence presence — they can no longer diverge.
- Still aligned with the integrity model: "View" (proof) appears only for
  genuinely-submitted, evidenced rows; non-submitted rows link to the apply page;
  everything else shows "—". Nothing implies a submission that didn't happen.

## Verification
- Frontend **build clean**.
- Backend tests **44 passed** (unchanged — no API touched).
- **Playwright 13/13 passed**, including **Activity Log** and **Verification Center**,
  with **0 console errors · 0 failed API requests · 0 uncaught exceptions**.
- Live data check: current rows (84 Tracked, 31 Manual Apply — no evidence) correctly
  render **Open ↗ → apply_url**; with no Submitted/Verified-with-evidence rows present,
  the "View" branch is exercised by the existing assisted-apply tests.
