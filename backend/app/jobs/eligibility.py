"""Eligibility scoring — "can THIS user realistically apply to THIS role?"

Distinct from match scoring (skills/role/location overlap), eligibility answers a
different question for early-career users (students / freshers / interns / new
grads): is this role at the right *level* and *accessibility*?

It BOOSTS internship / intern / student / new grad / graduate program / fresher /
entry-level / associate-engineer (especially AI-ML & software) and HIDES roles
out of reach for an early-career candidate:
  senior · staff · principal · lead · manager · director · architect ·
  3+ years experience · PhD-required · Master's-required.

Tiers: Excellent Match · Good Match · Possible Match · Not Recommended.
"Not Recommended" roles are hidden by default (for early-career profiles).

Pure, deterministic, no network. Penalties apply only to early-career profiles
(seeker_type student/fresher, or experience <= 2); experienced users are never
down-ranked by them.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Dict, List

_CURRENT_YEAR = datetime.now(timezone.utc).replace(tzinfo=None).year

# ---- level / accessibility signals ----
_SENIOR = re.compile(
    r"\b(senior|sr\.?|staff|principal|lead|manager|mgr|director|head\s+of|"
    r"vp|vice\s+president|architect|expert|distinguished|fellow)\b", re.I)
_EARLY = re.compile(
    r"\b(intern|internship|co-?op|apprentice|trainee|graduate\s+program|"
    r"new\s*grad|entry[-\s]?level|early\s+career|fresher|junior|campus|"
    r"university|student|associate\s+(?:software\s+)?engineer|associate\s+developer)\b",
    re.I)
_DOMAIN = re.compile(
    r"\b(software|engineer|developer|sde|swe|ai|ml|machine\s+learning|data\s+"
    r"scien|deep\s+learning|nlp|computer\s+vision|backend|frontend|full[-\s]?stack)\b", re.I)
_PHD = re.compile(r"\b(ph\.?d|doctoral|doctorate)\b", re.I)
_MASTERS_REQ = re.compile(
    r"(master'?s?\s+(?:degree\s+)?(?:is\s+)?(?:required|mandatory)|"
    r"\b(?:ms|m\.s\.|m\.?tech|mtech)\s+(?:degree\s+)?required|"
    r"requires?\s+(?:a\s+)?master'?s?|must\s+have\s+(?:a\s+)?master)", re.I)
_DEGREE_OPEN = re.compile(r"\b(bachelor|undergrad|b\.?tech|b\.?e\.?\b|all\s+degree|or\s+equivalent)", re.I)
_YEARS = re.compile(r"\b(\d{1,2})\s*\+?\s*(?:to\s*\d{1,2}\s*)?(?:years?|yrs?)\b", re.I)
_VISA = re.compile(
    r"(no\s+(?:visa\s+)?sponsorship|without\s+sponsorship|"
    r"must\s+be\s+(?:legally\s+)?authorized\s+to\s+work|"
    r"(?:us|u\.s\.|uk|eu)\s+citizen(?:s|ship)?\s+(?:only|required)|"
    r"security\s+clearance|do\s+not\s+(?:provide|offer)\s+sponsorship)", re.I)

# Tiers
EXCELLENT, GOOD, POSSIBLE, NOT_REC = (
    "Excellent Match", "Good Match", "Possible Match", "Not Recommended")

# ---- internship / new-grad hard-filter signals ----
# Ordered: the first matching group decides the displayed type badge.
_SIGNALS = [
    ("Internship", re.compile(r"\b(intern|internship)\b", re.I)),
    ("New Grad", re.compile(r"\b(new\s*grad(?:uate)?|graduate\s+program|"
                            r"university\s+graduate|campus)\b", re.I)),
    ("Fresher Friendly", re.compile(r"\b(fresher|entry[-\s]?level|associate\s+"
                                    r"(?:software\s+)?engineer|associate\s+developer|"
                                    r"trainee|apprentice|junior)\b", re.I)),
]


def early_signal(job) -> str:
    """Return the internship/new-grad badge label for a job, or '' if none.

    A job qualifies for the internships-&-new-grad hard filter iff this is
    non-empty (i.e. its title/snippet carries an explicit early-career signal).
    """
    title = job.get("title") if isinstance(job, dict) else str(job)
    desc = job.get("description_snippet", "") if isinstance(job, dict) else ""
    text = f"{title}\n{desc}"
    for label, rx in _SIGNALS:
        if rx.search(text):
            return label
    return ""


def has_internship_signal(job) -> bool:
    return bool(early_signal(job))


def internships_only_default(profile: dict) -> bool:
    """Default the hard filter ON for students / freshers / pre-graduation users."""
    st = (profile.get("seeker_type") or "").lower()
    if st in ("student", "fresher"):
        return True
    grad_year = int(profile.get("graduation_year", 0) or 0)
    if grad_year and grad_year >= _CURRENT_YEAR:
        return True
    return False


def _max_required_years(text: str) -> int:
    yrs = [int(m) for m in _YEARS.findall(text)]
    return max(yrs) if yrs else 0


def _is_early(profile: dict) -> bool:
    if (profile.get("seeker_type") or "").lower() in ("student", "fresher"):
        return True
    return int(profile.get("experience", 0) or 0) <= 2


def eligibility(job: dict, profile: dict) -> Dict:
    title = job.get("title") or ""
    desc = job.get("description_snippet") or ""
    hay = f"{title}\n{desc}"
    is_early = _is_early(profile)

    score = 60
    boosts: List[str] = []
    flags: List[str] = []
    disqualified = False

    early_role = bool(_EARLY.search(title)) or bool(_EARLY.search(desc))
    if early_role:
        score += 30
        boosts.append("Early-career role (internship / new grad / entry-level)")
    if _DOMAIN.search(title):
        score += 8
        boosts.append("Matches your AI/ML & software focus")

    if is_early:
        if _SENIOR.search(title):
            score -= 60
            disqualified = True
            m = _SENIOR.search(title)
            flags.append(f"{m.group(0).title()}-level role — above an early-career stage")
        if _PHD.search(hay) and not _DEGREE_OPEN.search(hay):
            score -= 60
            disqualified = True
            flags.append("PhD required — needs an active PhD")
        if _MASTERS_REQ.search(hay) and not _DEGREE_OPEN.search(hay):
            score -= 45
            disqualified = True
            flags.append("Master's degree required")
        req_years = _max_required_years(hay)
        if req_years >= 3:
            score -= min(req_years * 10, 55)
            disqualified = True
            flags.append(f"Requires ~{req_years}+ years of experience")
        if _VISA.search(desc):
            score -= 30
            flags.append("May require local work authorization (no visa sponsorship)")
    else:
        if _SENIOR.search(title):
            score += 6
            boosts.append("Seniority matches your experience")

    score = max(0, min(100, score))

    # ---- tier + hide ----
    if is_early and disqualified:
        tier, hide = NOT_REC, True
    elif score >= 80:
        tier, hide = EXCELLENT, False
    elif score >= 60:
        tier, hide = GOOD, False
    elif score >= 40:
        tier, hide = POSSIBLE, False
    else:
        tier, hide = NOT_REC, is_early

    # Lead with WHY: disqualifier first when not recommended, else the positive.
    if flags and (disqualified or tier in (NOT_REC, POSSIBLE)):
        reasons = flags + boosts
    else:
        reasons = boosts + flags
    if not reasons:
        reasons = ["No level restrictions detected"]

    return {
        "eligibility_score": score,
        "eligibility_tier": tier,
        "eligible": tier != NOT_REC,
        "eligibility_reason": reasons[0],
        "eligibility_reasons": reasons[:5],   # "Why matched?" bullets
        "hide": hide,
    }
