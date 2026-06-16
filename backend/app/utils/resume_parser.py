"""Resume PDF parsing using pdfplumber.

Extracts a structured profile: name, email, phone, location, skills, years of
experience, education, LinkedIn URL, and portfolio URL. Heuristic + regex based
so it runs anywhere with no ML dependency. Imperfect fields are corrected by the
user via the editable form on the Resume page.
"""
import re
from typing import Dict, List

import pdfplumber

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(
    # optional country code, then EITHER grouped digits (e.g. "98765 43210",
    # "(044) 2345 6789") OR a clean 10-digit run. Greedy enough to capture the
    # whole number (the caller validates digit count) — fixes 5-5 truncation.
    r"(?:(?:\+|00)\d{1,3}[\s.\-]?)?"
    r"(?:\(?\d{2,5}\)?(?:[\s.\-]\d{2,5}){1,3}|(?<!\d)\d{10}(?!\d))"
)
EXP_RE = re.compile(r"(\d{1,2})\+?\s*(?:years?|yrs?)", re.IGNORECASE)
LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/(?:in|pub)/[A-Za-z0-9_\-%/]+", re.I)
URL_RE = re.compile(r"https?://[^\s)\]}>,]+", re.I)
GITHUB_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9_\-]+", re.I)

SKILL_KEYWORDS = [
    "python", "java", "javascript", "typescript", "react", "angular", "vue",
    "node", "node.js", "express", "django", "flask", "fastapi", "spring",
    "sql", "mysql", "postgresql", "mongodb", "redis", "sqlite",
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ci/cd",
    "git", "linux", "html", "css", "tailwind", "sass",
    "machine learning", "deep learning", "tensorflow", "pytorch", "nlp",
    "data analysis", "pandas", "numpy", "excel", "power bi", "tableau",
    "c++", "c#", "go", "golang", "rust", "php", "ruby", "kotlin", "swift",
    "rest api", "graphql", "microservices", "agile", "scrum",
    "communication", "leadership", "project management", "selenium", "playwright",
    "figma", "ui/ux", "product management", "spark", "hadoop", "kafka",
]

DEGREE_KEYWORDS = [
    "bachelor", "master", "ph.d", "phd", "b.tech", "btech", "b.e", "m.tech",
    "mtech", "b.sc", "m.sc", "bsc", "msc", "mba", "b.a", "m.a", "bca", "mca",
    "diploma", "associate degree", "high school",
]

# Common Indian + global city hints for a light location guess.
LOCATION_HINTS = [
    "bangalore", "bengaluru", "mumbai", "delhi", "new delhi", "hyderabad",
    "chennai", "pune", "kolkata", "ahmedabad", "noida", "gurgaon", "gurugram",
    "jaipur", "trichy", "tiruchirappalli", "coimbatore", "kochi", "remote",
    "dubai", "abu dhabi", "singapore", "london", "new york", "san francisco",
    "berlin", "toronto", "sydney",
]


def _extract_text(file_path: str) -> str:
    parts = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts)


# Words that signal a line is a project/section header, not a person's name.
_NON_NAME_WORDS = {
    "prediction", "system", "systems", "model", "models", "analysis", "detection",
    "using", "project", "projects", "developer", "engineer", "intern", "internship",
    "resume", "curriculum", "vitae", "portfolio", "framework", "application",
    "based", "platform", "management", "experience", "education", "skills",
    "summary", "objective", "profile", "contact", "arena", "invisible", "data",
    "machine", "learning", "heat", "stress", "fraud", "cache", "semantic",
}


def _guess_name(text: str, email: str) -> str:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for line in lines[:12]:
        words = line.split()
        if not (1 < len(words) <= 4):
            continue
        if "@" in line or any(c.isdigit() for c in line):
            continue
        lw = [w.lower().strip(".,") for w in words]
        if any(w in _NON_NAME_WORDS for w in lw):
            continue
        if all(re.match(r"^[A-Za-z.'-]+$", w) for w in words):
            return line.title()
    # Fall back to deriving a name from a firstname.lastname style email.
    if email:
        local = email.split("@")[0]
        if re.search(r"[._]", local):
            return re.sub(r"[._\d]+", " ", local).strip().title()
    return ""


def _guess_location(text: str) -> str:
    low = text.lower()
    for hint in LOCATION_HINTS:
        if re.search(r"\b" + re.escape(hint) + r"\b", low):
            return hint.title()
    return ""


def _extract_education(text: str) -> List[Dict[str, str]]:
    out = []
    seen = set()
    for line in text.splitlines():
        low = line.lower()
        if any(d in low for d in DEGREE_KEYWORDS):
            clean = re.sub(r"\s+", " ", line).strip(" •-\t")
            key = clean.lower()[:60]
            if clean and key not in seen and len(clean) < 160:
                seen.add(key)
                # Try to pull a year.
                year = ""
                m = re.search(r"(19|20)\d{2}", clean)
                if m:
                    year = m.group(0)
                out.append({"detail": clean, "year": year})
        if len(out) >= 5:
            break
    return out


def _portfolio_url(text: str, linkedin: str, github: str) -> str:
    for m in URL_RE.finditer(text):
        url = m.group(0).rstrip(".,);")
        low = url.lower()
        if "linkedin.com" in low:
            continue
        if "@" in url:  # stray email-in-url
            continue
        # Prefer a personal site / github / portfolio host.
        if any(h in low for h in ("github.com", "behance", "dribbble", "vercel.app",
                                  "netlify.app", "portfolio", "github.io", "notion.site")):
            return url
    # Fall back to github if present.
    return github or ""


def parse_resume(file_path: str) -> dict:
    try:
        text = _extract_text(file_path)
    except Exception:
        text = ""

    lowered = text.lower()

    email_m = EMAIL_RE.search(text)
    email = email_m.group(0) if email_m else ""

    phone = ""
    for m in PHONE_RE.finditer(text):
        raw = m.group(0).strip()
        digits = re.sub(r"[^\d+]", "", raw).lstrip("+")
        has_plus = raw.strip().startswith("+")
        has_sep = bool(re.search(r"[\s\-()]", raw))
        # Accept only things that actually look like phone numbers: an explicit
        # country code, separators, or a clean 10-digit mobile. This rejects long
        # digit blobs like registration / roll numbers.
        if has_plus and 9 <= len(digits) <= 15:
            phone = raw
            break
        if has_sep and 10 <= len(digits) <= 13:
            phone = raw
            break
        if len(digits) == 10:
            phone = raw
            break

    experience = 0
    exp_matches = [int(m) for m in EXP_RE.findall(text) if int(m) < 60]
    if exp_matches:
        experience = max(exp_matches)

    skills = []
    for kw in SKILL_KEYWORDS:
        if re.search(r"\b" + re.escape(kw) + r"\b", lowered):
            skills.append(kw.title())
    skills = list(dict.fromkeys(skills))

    linkedin_m = LINKEDIN_RE.search(text)
    linkedin = linkedin_m.group(0) if linkedin_m else ""
    if linkedin and not linkedin.lower().startswith("http"):
        linkedin = "https://" + linkedin

    github_m = GITHUB_RE.search(text)
    github = github_m.group(0) if github_m else ""
    if github and not github.lower().startswith("http"):
        github = "https://" + github

    portfolio = _portfolio_url(text, linkedin, github)

    return {
        "parsed_name": _guess_name(text, email),
        "parsed_email": email,
        "parsed_phone": phone,
        "parsed_location": _guess_location(text),
        "parsed_skills": skills,
        "parsed_experience": experience,
        "parsed_education": _extract_education(text),
        "linkedin_url": linkedin,
        "portfolio_url": portfolio,
        "raw_text": text[:12000],  # cap for storage / AI context
    }
