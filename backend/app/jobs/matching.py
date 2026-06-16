"""Job match scoring.

Computes a 0-100 fit score for a job against the user's parsed profile +
filters, with a human-readable breakdown. Pure, deterministic, no network.

Weighting:
  skills     45   overlap between profile skills and the job
  role/title 30   desired roles/keywords appearing in the title
  location   15   location preference alignment
  experience 10   seniority alignment
"""
from __future__ import annotations

import re
from typing import Dict, List

_SENIOR = ("senior", "lead", "staff", "principal", "head", "manager", "director")
_JUNIOR = ("intern", "junior", "graduate", "entry", "trainee", "associate")


def _tokens(text: str) -> set:
    return set(re.findall(r"[a-z0-9+#.]+", (text or "").lower()))


def score_job(job: dict, profile: dict) -> Dict:
    skills: List[str] = [s.lower() for s in profile.get("skills", []) if s]
    roles: List[str] = [r.lower() for r in profile.get("roles", []) if r]
    keywords: List[str] = [k.lower() for k in profile.get("keywords", []) if k]
    locations: List[str] = [l.lower() for l in profile.get("locations", []) if l]
    exp_years: int = int(profile.get("experience", 0) or 0)

    title = (job.get("title") or "").lower()
    hay = f"{title} {job.get('company','')} {job.get('description_snippet','')}".lower()
    hay_tokens = _tokens(hay)
    job_loc = (job.get("location") or "").lower()

    reasons: List[str] = []

    # --- skills (45) ---
    skill_score = 0.0
    if skills:
        matched = [s for s in skills if s in hay or _tokens(s) & hay_tokens]
        ratio = len(matched) / max(len(skills), 1)
        skill_score = min(ratio * 1.4, 1.0) * 45  # reward partial overlap generously
        if matched:
            reasons.append(f"{len(matched)} skill match: {', '.join(matched[:5])}")
    else:
        skill_score = 18  # neutral baseline when no skills parsed

    # --- role/title (30) ---
    role_terms = roles + keywords
    role_score = 0.0
    if role_terms:
        hit = False
        for term in role_terms:
            words = [w for w in re.split(r"\s+", term) if w]
            if term in title or (words and all(w in title for w in words)):
                role_score = 30
                hit = True
                reasons.append(f"Title matches “{term}”")
                break
            if any(w in title for w in words):
                role_score = max(role_score, 18)
        if not hit and role_score == 0:
            # term appears anywhere in the listing
            if any(t in hay for t in role_terms):
                role_score = 12
    else:
        role_score = 15

    # --- location (15) ---
    loc_score = 0.0
    if locations:
        if any(l in job_loc for l in locations):
            loc_score = 15
            reasons.append("Location match")
        elif job.get("remote") or "remote" in job_loc:
            loc_score = 12
            reasons.append("Remote-friendly")
        else:
            loc_score = 4
    else:
        loc_score = 10

    # --- experience (10) ---
    exp_score = 7  # neutral
    if any(s in title for s in _SENIOR):
        exp_score = 10 if exp_years >= 4 else (5 if exp_years >= 2 else 2)
    elif any(s in title for s in _JUNIOR):
        exp_score = 10 if exp_years <= 3 else 6

    total = round(skill_score + role_score + loc_score + exp_score)
    total = max(0, min(100, total))

    return {"score": total, "reasons": reasons[:4]}
