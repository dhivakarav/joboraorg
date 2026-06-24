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
QUEUED = "Queued"                  # auto-submission enqueued / in flight
SUBMITTED = "Submitted"
VERIFIED = "Verified Submitted"
FAILED = "Failed"

# User-reported POST-submission lifecycle stages. SELF-REPORTED by the user (not
# evidence of an automated submission) — the human funnel they track by hand.
# Automation NEVER sets these. Note "Applied" is deliberately NOT here: it
# collides with the retired auto-label, so a stale legacy "Applied" could not be
# told apart from a user-set one — the truthful equivalents are Tracked/Submitted.
INTERVIEW = "Interview"
OFFER = "Offer"
REJECTED = "Rejected"
PIPELINE_STAGES = {INTERVIEW, OFFER, REJECTED}

# Every stage a user may self-assign in the Activity Log. SINGLE source of truth:
# the API validates PATCH against this, and it's returned to the UI verbatim as
# `pipeline_stage` so the Stage dropdown reflects exactly what was saved — unlike
# display_status(), which (correctly) prioritises submission_status for its column.
SAVED = "Saved"
SKIPPED = "Skipped"
USER_SETTABLE_STAGES = {SAVED, TRACKED, SKIPPED, INTERVIEW, OFFER, REJECTED}


def pipeline_stage(app) -> str:
    """The raw user-set pipeline stage if one is set, else "".

    Independent of submission_status, so picking Saved/Skipped/Tracked round-trips
    on the Stage dropdown just like Interview/Offer/Rejected already do. The stage
    lives in the legacy `status` column (only the user sets these values; automation
    writes lifecycle hints like 'Pending'/'Submitted', which are NOT in the set)."""
    legacy = (getattr(app, "status", "") or "").strip()
    return legacy if legacy in USER_SETTABLE_STAGES else ""

# A submission that was attempted/recorded but carries NO evidence (no id, no
# confirmation URL, no screenshot) — e.g. historical rows submitted before evidence
# capture existed. It can NEVER graduate to Verified (you can't screenshot the
# past), so it is shown distinctly rather than lumped with evidenced submissions.
SUBMITTED_UNVERIFIED = "Submitted (Unverified)"

# Auto-capable job discovered by "Start Applying" but NOT yet submitted — it is
# waiting for the user's explicit per-job/batch approval. Real submission only
# happens after the user confirms (permanent safety gate, even in live mode).
PENDING_APPROVAL = "Pending Approval"

# Specific auto-apply failure labels (a live attempt that produced no real
# confirmation). Distinct so the user sees WHY an attempt didn't go through.
FAILED_NO_CONFIRMATION = "Failed — No Confirmation"
FAILED_FORM_NOT_FOUND = "Failed — Form Not Found"
FAILED_SUBMIT_NOT_FOUND = "Failed — Submit Not Found"
FAILURE_LABELS = {FAILED_NO_CONFIRMATION, FAILED_FORM_NOT_FOUND, FAILED_SUBMIT_NOT_FOUND}

CANONICAL = [DRAFT, TRACKED, MANUAL, PENDING_APPROVAL, QUEUED, SUBMITTED,
             SUBMITTED_UNVERIFIED, VERIFIED, FAILED, FAILED_NO_CONFIRMATION,
             FAILED_FORM_NOT_FOUND, FAILED_SUBMIT_NOT_FOUND,
             INTERVIEW, OFFER, REJECTED]


def evidence_complete(app) -> bool:
    """True iff the three hard proofs of a verified submission are all present:
    an application/reference id, a confirmation URL, and a stored evidence file.
    """
    app_id = getattr(app, "application_id", "") or getattr(app, "external_application_id", "")
    conf = getattr(app, "confirmation_url", "") or ""
    evid = bool(getattr(app, "evidence_available", False))
    return bool(app_id and conf and evid)


def has_any_evidence(app) -> bool:
    """True if ANY proof exists (id, confirmation URL, or stored screenshot)."""
    return bool(getattr(app, "application_id", "")
                or getattr(app, "external_application_id", "")
                or getattr(app, "confirmation_url", "")
                or getattr(app, "evidence_available", False))


def display_status(app) -> str:
    """Derive the canonical, user-safe status from a stored Application.

    This is the ONLY function any view should use to decide what to show. It can
    never return "Verified Submitted" without complete evidence, and can never
    return "Applied" at all.
    """
    ss = (getattr(app, "submission_status", "") or "").strip()
    legacy = (getattr(app, "status", "") or "").strip()
    manual = bool(getattr(app, "manual_required", False))

    # User-reported pipeline stage wins: someone who reached Interview/Offer wants
    # to see that, not the derived submission status. These are only ever set by
    # the user via PATCH /applications/{id}/status (never by automation).
    if legacy in PIPELINE_STAGES:
        return legacy

    # Awaiting the user's explicit approval before any real submission.
    if ss == "Pending Approval":
        return PENDING_APPROVAL

    # Specific failure labels surface as-is (e.g. "Failed — No Confirmation").
    if ss in FAILURE_LABELS:
        return ss

    # Positive terminal states, gated on evidence:
    #   • all three proofs   → Verified Submitted
    #   • some proof         → Submitted (attempted, partially evidenced)
    #   • no proof at all    → Submitted (Unverified)  (e.g. pre-evidence history)
    if ss in ("Verified Submitted", "Submitted"):
        if evidence_complete(app):
            return VERIFIED
        return SUBMITTED if has_any_evidence(app) else SUBMITTED_UNVERIFIED
    if ss in ("Queued", "Processing"):
        # An auto-submission is enqueued/in flight — show it honestly as Queued.
        return QUEUED
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
