"""Resume ⇄ job matching engine (hybrid model).

Pure, deterministic, no network. Compares a parsed resume (skills, desired roles,
years of experience) against a job's title + description and returns a 0-100
match_score with a human-readable breakdown, using:

  • keyword/skill overlap  (resume skills found in the job)        — up to 55
  • title/role similarity  (desired role/title terms in the title) — up to 30
  • experience alignment   (seniority vs the user's experience)    — up to 15

A configurable minimum threshold (Filters page, default 50) decides whether a
job is shown/stored.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

DEFAULT_MIN_MATCH_SCORE = 50

_SENIOR = ("senior", "lead", "staff", "principal", "head", "manager", "director", "vp")
_JUNIOR = ("intern", "internship", "junior", "graduate", "new grad", "entry", "trainee",
           "fresher", "associate")

# Leadership / executive titles. These are NOT a relevant match for a specific
# individual-contributor technical search (e.g. "data engineer") just because they
# share a word like "engineering" — unless the user actually searched for a
# leadership role. (Distinct from seniority modifiers like "Senior Data Engineer",
# which IS still a data engineer and must keep matching.)
_LEADERSHIP = re.compile(
    r"\b(vp|vice\s*president|director|head\s+of|chief|president|"
    r"c[teofi]o|cxo|partner|founder)\b", re.I)


def _tokens(text: str) -> set:
    return set(re.findall(r"[a-z0-9+#.]+", (text or "").lower()))


def match_score(resume_skills: List[str], job_title: str, job_description: str = "",
                years_experience: int = 0, desired_roles: Optional[List[str]] = None) -> Dict:
    """Return {'score': 0-100, 'reasons': [...]} for a resume vs a job."""
    skills = [s.lower().strip() for s in (resume_skills or []) if s and s.strip()]
    roles = [r.lower().strip() for r in (desired_roles or []) if r and r.strip()]
    title = (job_title or "").lower()
    hay = f"{title} {job_description or ''}".lower()
    hay_tokens = _tokens(hay)
    reasons: List[str] = []

    # --- skill / keyword overlap (55) ---
    if skills:
        matched = [s for s in skills if s in hay or _tokens(s) & hay_tokens]
        ratio = len(matched) / max(len(skills), 1)
        skill_score = min(ratio * 1.4, 1.0) * 55           # reward partial overlap
        if matched:
            reasons.append(f"{len(matched)}/{len(skills)} skills match: {', '.join(matched[:5])}")
    else:
        skill_score = 22                                   # neutral when no skills parsed

    # --- title / role similarity (30) ---
    # Guard: a leadership/executive title (VP, Director, Head of, Chief, …) is not a
    # match for a non-leadership technical role search — block the role credit and
    # the "Title matches" reason so a shared word ("engineering") can't make a VP
    # look like a Data/Software Engineer match. Unless the search itself is for a
    # leadership role, in which case let it match normally.
    title_is_leadership = bool(_LEADERSHIP.search(title))
    wants_leadership = any(_LEADERSHIP.search(r) for r in roles)
    if roles and title_is_leadership and not wants_leadership:
        role_score = 0          # off-target leadership title → no role credit, no reason
    elif roles:
        role_score = 0.0
        for term in roles:
            words = [w for w in re.split(r"\s+", term) if w]
            if term in title or (words and all(w in title for w in words)):
                role_score = 30
                reasons.append(f"Title matches “{term}”")
                break
            if any(w in title for w in words):
                role_score = max(role_score, 18)
        if role_score == 0 and any(t in hay for t in roles):
            role_score = 12
    else:
        role_score = 15

    # --- experience alignment (15) ---
    exp_score = 10
    if any(s in title for s in _SENIOR):
        exp_score = 15 if years_experience >= 4 else (7 if years_experience >= 2 else 3)
    elif any(s in title for s in _JUNIOR):
        exp_score = 15 if years_experience <= 3 else 9

    total = max(0, min(100, round(skill_score + role_score + exp_score)))
    # Off-target leadership/executive title vs a non-leadership search: cap the score
    # well below any sensible match threshold so it's excluded everywhere (Find Jobs,
    # the auto-apply engine, and Matched Jobs), even if its résumé skills overlap.
    if roles and title_is_leadership and not wants_leadership:
        total = min(total, 15)
    return {"score": total, "reasons": reasons[:4]}


def score_job(job: dict, profile: dict, query: str = "") -> Dict:
    """Adapter for the existing call shape: score a job dict against a profile.

    When the user typed an explicit search `query`, it becomes the PRIMARY desired
    role so the score, ranking, and "Why matched?" reasons reflect what was actually
    searched for (e.g. "data engineer") — not just the stored profile roles (e.g.
    "software engineer"). Without a query, behaviour is unchanged.
    """
    roles = (profile.get("roles", []) or []) + (profile.get("keywords", []) or [])
    if query and query.strip():
        roles = [query.strip()] + roles
    return match_score(
        resume_skills=profile.get("skills", []),
        job_title=job.get("title", ""),
        job_description=job.get("description_snippet", "") or job.get("company", ""),
        years_experience=int(profile.get("experience", 0) or 0),
        desired_roles=roles,
    )


def meets_threshold(score: int, minimum: Optional[int] = None) -> bool:
    return score >= (DEFAULT_MIN_MATCH_SCORE if minimum is None else minimum)
