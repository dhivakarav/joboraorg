"""India-first discovery signals + filters.

Pure, deterministic helpers used to (a) boost India + priority-domain roles in
ranking, and (b) apply the company / salary / internship-duration filters. No
network. Keeps the India-first logic in one testable place.
"""
from __future__ import annotations

import re
from typing import Optional

# Major Indian hubs (+ generic "india"). Used for location relevance.
INDIA_HUBS = (
    "chennai", "bangalore", "bengaluru", "hyderabad", "pune", "mumbai", "delhi",
    "new delhi", "gurgaon", "gurugram", "noida", "kolkata", "ahmedabad",
    "coimbatore", "kochi", "trichy", "tiruchirappalli", "jaipur", "india",
)

# City synonyms / groupings so a user's filter matches how providers label jobs
# (Google for Jobs returns "Bengaluru", "Gurugram", "…, IN"). Each filter key maps
# to the set of substrings that should count as that place.
CITY_ALIASES = {
    "bangalore": ("bangalore", "bengaluru"),
    "bengaluru": ("bangalore", "bengaluru"),
    "gurgaon": ("gurgaon", "gurugram"),
    "gurugram": ("gurgaon", "gurugram"),
    "delhi": ("delhi", "new delhi"),
    "delhi ncr": ("delhi", "new delhi", "noida", "gurgaon", "gurugram",
                  "ghaziabad", "faridabad"),
}


def _is_india(loc: str) -> bool:
    """True when a job location is in India — including the bare ISO country code
    ('IN') and the '…, IN' suffix that Google for Jobs / JSearch emit, which the
    literal word 'india' never matches."""
    loc = (loc or "").lower().strip()
    if not loc:
        return False
    if loc == "in" or loc.endswith(", in") or loc.endswith(",in"):
        return True
    return any(h in loc for h in INDIA_HUBS)


def is_india_filter(filter_loc: str) -> bool:
    """True when a user's location filter is India-related (so India-aware
    matching should apply instead of plain substring)."""
    f = (filter_loc or "").lower().strip()
    return f in ("india", "remote india") or f in CITY_ALIASES or \
        any(h in f for h in INDIA_HUBS)


def india_location_matches(filter_loc: str, job_loc: str, remote: bool = False) -> bool:
    """India-aware location match used by the discovery filter.

    - 'India'        → any India-located role (incl. '…, IN') or a location-agnostic remote role.
    - 'Remote India' → remote roles or India-located roles.
    - a city         → that city (with synonyms, e.g. Bangalore↔Bengaluru, Delhi NCR group).
    """
    f = (filter_loc or "").lower().strip()
    jl = (job_loc or "").lower()
    if f == "india":
        return _is_india(jl) or (remote and not jl)
    if f == "remote india":
        return remote or "remote" in jl or _is_india(jl)
    names = CITY_ALIASES.get(f, (f,))
    return any(n in jl for n in names)

# Priority domains for the target audience (AI/ML, SWE, DS, Backend, Full Stack).
PRIORITY_DOMAIN = re.compile(
    r"\b(ai|ml|machine\s*learning|deep\s*learning|data\s*scien(?:ce|tist)|"
    r"data\s*analyst|nlp|computer\s*vision|software\s*engineer|sde|swe|"
    r"back[-\s]?end|front[-\s]?end|full[-\s]?stack|developer|programmer)\b", re.I)

_SAL = re.compile(r"([\d][\d,]*(?:\.\d+)?)\s*(cr|crore|l|lakh|k)?", re.I)


def is_india_location(location: str, remote: bool = False) -> bool:
    if _is_india(location):
        return True
    return bool(remote and "india" in (location or "").lower())


def india_bonus(location: str, remote: bool = False) -> float:
    """Ranking bonus for India relevance (an India location > generic remote)."""
    if _is_india(location):
        return 25.0
    if remote:
        return 8.0   # remote roles may be India-accessible
    return 0.0


def domain_bonus(title: str) -> float:
    """Ranking bonus when the title is a priority domain (AI/ML/SWE/DS/Backend/Fullstack)."""
    return 15.0 if PRIORITY_DOMAIN.search(title or "") else 0.0


# India-first ranking tiers (lower = ranked higher). The tier is the PRIMARY sort
# key, so India always precedes global regardless of match score; within a tier the
# existing relevance order (match/eligibility/domain) is preserved.
TIER_INDIA = 1        # India-located, on-site (e.g. "Bengaluru, India")
TIER_INDIA_REMOTE = 2  # India-located AND remote (e.g. "Remote, India")
TIER_GLOBAL = 3       # everything else (US/EU/global, incl. non-India remote)


def india_tier(location: str, remote: bool = False) -> int:
    """India-first ranking tier for a job.

    Tier 1 = India on-site, Tier 2 = India-remote, Tier 3 = global. A job counts as
    India when its location is India-tagged (city/hub or the ', IN' / 'IN' country
    code that Google for Jobs emits); a non-India 'Remote' role is global (Tier 3),
    NOT India-remote.
    """
    if _is_india(location):
        return TIER_INDIA_REMOTE if remote else TIER_INDIA
    return TIER_GLOBAL


def company_match(company: str, wanted: str) -> bool:
    """Case-insensitive substring company filter (empty filter = match all)."""
    if not wanted:
        return True
    return wanted.strip().lower() in (company or "").lower()


def salary_inr_annual(salary_inr: str) -> Optional[int]:
    """Best-effort parse of a formatted INR salary → approximate ANNUAL rupees.

    Handles '₹3 L', '₹1.75 Cr', '₹20,000/month', '₹6L - ₹10L' (takes the first
    figure). Returns None when nothing parseable (so unknown-salary jobs are kept,
    not filtered out).
    """
    if not salary_inr:
        return None
    t = salary_inr.lower().replace("₹", " ")
    m = _SAL.search(t)
    if not m:
        return None
    try:
        num = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    unit = (m.group(2) or "").lower()
    if unit in ("cr", "crore"):
        val = num * 10_000_000
    elif unit in ("l", "lakh"):
        val = num * 100_000
    elif unit == "k":
        val = num * 1_000
    else:
        val = num
    if "month" in t or "/mo" in t or " pm" in t or "per month" in t:
        val *= 12   # annualize monthly figures for comparison
    return int(val)


def passes_salary(salary_inr: str, min_annual: int) -> bool:
    """Keep jobs whose salary is unknown OR meets the annual floor (never exclude
    unknown-salary roles — most internships don't publish pay)."""
    if not min_annual:
        return True
    val = salary_inr_annual(salary_inr)
    return val is None or val >= min_annual


def duration_match(duration: str, wanted: str) -> bool:
    """Internship-duration filter. Duration data is sparse from aggregators, so a
    job with NO declared duration is kept; one that declares a duration must match
    the requested bucket (e.g. '3' months)."""
    if not wanted:
        return True
    d = (duration or "").lower()
    if not d:
        return True   # unknown duration — don't exclude
    return wanted.lower() in d
