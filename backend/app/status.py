"""Canonical application status — the SINGLE source of truth for what users see.

Integrity rule (non-negotiable): a UI/API never reports a positive "submitted"
outcome unless real evidence exists. The only positive terminal status is
**Verified Submitted**, and it requires an application id + a confirmation URL +
a stored evidence artifact. The legacy "Applied" label is retired everywhere.

Canonical statuses (the only values any screen may display):
  Draft               saved only — no submission attempted
  Tracked             monitored — user is following this job
  Manual Apply        the user must submit on the platform
  Submitted           a submission was attempted (no confirmation yet)
  Verified Submitted  application id + confirmation evidence exists
  Failed              a submission attempt failed
"""
from __future__ import annotations

DRAFT = "Draft"
TRACKED = "Tracked"
MANUAL = "Manual Apply"
SUBMITTED = "Submitted"
VERIFIED = "Verified Submitted"
FAILED = "Failed"

CANONICAL = [DRAFT, TRACKED, MANUAL, SUBMITTED, VERIFIED, FAILED]

# User-settable outcomes are out of scope here; this module governs only the
# system-derived application status. "Applied" deliberately does NOT exist.


def evidence_complete(app) -> bool:
    """True iff the three hard proofs of a verified submission are all present:
    an application/reference id, a confirmation URL, and a stored evidence file.
    """
    app_id = getattr(app, "application_id", "") or getattr(app, "external_application_id", "")
    conf = getattr(app, "confirmation_url", "") or ""
    evid = bool(getattr(app, "evidence_available", False))
    return bool(app_id and conf and evid)


def display_status(app) -> str:
    """Derive the canonical, user-safe status from a stored Application.

    This is the ONLY function any view should use to decide what to show. It can
    never return "Verified Submitted" without complete evidence, and can never
    return "Applied" at all.
    """
    ss = (getattr(app, "submission_status", "") or "").strip()
    legacy = (getattr(app, "status", "") or "").strip()
    manual = bool(getattr(app, "manual_required", False))

    # Positive terminal state — gated on real evidence; otherwise downgraded.
    if ss == "Verified Submitted":
        return VERIFIED if evidence_complete(app) else SUBMITTED
    if ss == "Submitted":
        return SUBMITTED
    if ss in ("Queued", "Processing"):
        # An attempt is in flight/has begun — honest "Submitted", never "Applied".
        return SUBMITTED
    if ss in ("Failed", "CAPTCHA Required"):
        return FAILED
    if ss in ("Manual Apply", "Manual Apply Required") or manual:
        return MANUAL

    # No submission attempted (Draft / Ready / empty submission_status).
    # Distinguish a bare save from an actively-monitored job. Any legacy
    # "Applied"/"Submitted"/"Pending" WITHOUT evidence collapses to Tracked —
    # this is the guard that makes a stale "Applied" impossible to surface.
    if legacy == "Saved":
        return DRAFT
    if legacy in ("Tracked", "Applied", "Submitted", "Pending"):
        return TRACKED
    return DRAFT
