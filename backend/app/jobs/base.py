"""Core types for the real-job aggregation layer.

Every provider returns a list of ``RawJob`` objects. The aggregator normalises,
dedupes, verifies, and serialises them. Nothing here is mock data — each job
carries a real ``apply_url`` pointing at the genuine application page.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlparse

from . import india

# Title-based employment-type inference, so Internship/Fresher tabs surface real
# roles from sources (Greenhouse, Lever, Remotive, ...) that don't tag the type.
_INTERN_RE = re.compile(r"\b(intern|internship|industrial trainee|co-?op)\b", re.I)
_FRESHER_RE = re.compile(
    r"\b(new ?grad(uate)?|entry[\s-]?level|fresher|junior|jr\.?|graduate (engineer|analyst|developer|program)|campus|early[\s-]?career|trainee|associate)\b",
    re.I,
)


def infer_employment_type(title: str, existing: str = "") -> str:
    if existing:
        return existing
    t = title or ""
    if _INTERN_RE.search(t) and "internal" not in t.lower() and "international" not in t.lower():
        return "internship"
    if _FRESHER_RE.search(t):
        return "fresher"
    return "job"


@dataclass
class RawJob:
    source: str                      # provider name, e.g. "Greenhouse"
    title: str
    company: str
    apply_url: str                   # real application URL
    location: str = ""
    salary: str = ""
    deadline: str = ""               # ISO date string if known
    posted_at: str = ""              # ISO date string if known
    remote: bool = False
    job_type: str = ""
    description_snippet: str = ""
    external_id: str = ""            # provider-native id (for stable dedupe)
    company_domain: str = ""         # host that should own the apply URL
    source_domain: str = ""          # platform domain the apply URL lives on (derived if empty)
    employment_type: str = ""        # "internship" | "fresher" | "job" | ""
    duration: str = ""               # e.g. "3 months" (internships)

    # ---- derived ----
    @property
    def fingerprint(self) -> str:
        """Stable hash used for dedupe + application linkage."""
        basis = self.external_id or f"{self.source}|{self.company}|{self.title}|{self.apply_url}"
        return hashlib.sha256(basis.lower().encode()).hexdigest()[:32]

    def is_valid(self) -> bool:
        if not (self.title and self.company and self.apply_url):
            return False
        parsed = urlparse(self.apply_url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)

    def verify(self) -> bool:
        """A job is 'Verified' when it comes from an official source API and its
        apply URL is a well-formed https link to a real host. Optionally the host
        must match the expected company domain when the provider supplies one.
        """
        if not self.is_valid():
            return False
        parsed = urlparse(self.apply_url)
        if parsed.scheme != "https":
            return False
        if self.company_domain:
            host = parsed.netloc.lower()
            dom = self.company_domain.lower().lstrip("www.")
            # Apply URL may be on the company domain or the ATS's domain — both
            # are legitimate (ATS pages are the official application path).
            ats_hosts = ("greenhouse.io", "lever.co", "ashbyhq.com",
                         "myworkdayjobs.com", "remotive.com", "arbeitnow.com",
                         "adzuna", "jooble")
            if dom not in host and not any(a in host for a in ats_hosts):
                return False
        return True

    def _source_domain(self) -> str:
        """Domain the apply URL lives on (e.g. boards.greenhouse.io, jobs.lever.co).
        Falls back to the declared source_domain/company_domain, else ''."""
        if self.source_domain:
            return self.source_domain
        host = (urlparse(self.apply_url).netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
        return host or self.company_domain

    def to_dict(self) -> dict:
        from .currency import salary_to_inr_sync  # local import avoids cycle
        salary = self.salary.strip()
        return {
            "fingerprint": self.fingerprint,
            "external_id": self.external_id,
            "source": self.source,
            "source_domain": self._source_domain(),
            "title": self.title.strip(),
            "company": self.company.strip(),
            "location": self.location.strip() or ("Remote" if self.remote else ""),
            "salary": salary,
            "salary_inr": salary_to_inr_sync(salary),
            "deadline": self.deadline,
            "posted_at": self.posted_at,
            "remote": self.remote,
            "job_type": self.job_type,
            "employment_type": infer_employment_type(self.title, self.employment_type),
            "duration": self.duration,
            "apply_url": self.apply_url,
            # Keep enough description text for the resume matcher to differentiate
            # roles by their actual skill requirements (titles alone don't).
            "description_snippet": _clean(self.description_snippet)[:600],
            "verified": self.verify(),
        }


class Provider:
    """Base class for a real job source."""

    name: str = "Base"
    requires_key: bool = False
    # Official documented API → no scraping / robots concerns.
    official_api: bool = True
    # True when fetch() ignores the query (returns a broad list filtered later).
    # Lets the aggregator cache the raw fetch ONCE and reuse it for ALL queries.
    query_agnostic: bool = False

    def available(self) -> bool:
        """Whether this provider is configured and usable."""
        return True

    def status(self) -> str:
        """Human-facing connection status for the sources UI.

        Providers with richer lifecycles (e.g. Internshala: Mock Mode vs an
        authorized feed) override this. Default: Connected when usable, else
        Disabled.
        """
        return "Connected" if self.available() else "Disabled"

    def status_message(self) -> str:
        """Plain-language explanation of the current status, so the UI never shows
        a dead source without saying why / what it does. Providers with a richer
        lifecycle (Internshala, JSearch, Jooble) override this."""
        if self.available():
            return f"Connected to {self.name} (official public API)."
        if self.requires_key:
            return (f"{self.name} is off because it needs an API key/token. It surfaces "
                    f"no jobs until configured — no fake listings are shown.")
        return f"{self.name} is currently unavailable; it surfaces no jobs."

    async def fetch(self, client, query: str, location: str, limit: int) -> List[RawJob]:
        raise NotImplementedError


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

# HARD markers of a generic search / results / homepage URL (never a real job).
_SEARCH_URL_RE = re.compile(
    r"(searchterm=|[?&]q=|[?&]query=|[?&]keywords=|/job-search/|/jobs/search|"
    r"/srp/results)", re.I)

# SOFT markers — SEO category slugs like "-jobs-in-dubai" or "/internships/".
# These appear in BOTH category pages AND specific listings (job boards bake the
# search phrase into the listing's slug). Treat as generic ONLY when no specific
# job-id token is present.
_SOFT_LISTING_RE = re.compile(
    r"(-jobs-in-|/internships?/|/jobs-in-|-jobs(?:/|$|\?))", re.I)
# A real listing carries a stable id: a long digit run, or jid-/jobid/-id tokens.
_JOB_ID_RE = re.compile(r"(\d{5,}|jid[-_=]|job[_-]?id|/jobs?/\d+)", re.I)


def is_specific_job_url(url: str) -> bool:
    """True only if the URL points to a SPECIFIC job application page — not a
    portal homepage, search results, or category-listing page. Used to ensure
    every row a user sees has a real, clickable, specific apply link."""
    if not url:
        return False
    p = urlparse(url)
    host = (p.netloc or "").lower()
    if not host or "localhost" in host or "127.0.0.1" in host:
        return False                      # malformed or local mock URL
    if not (p.path or "").rstrip("/"):
        return False                      # bare domain / homepage
    if _SEARCH_URL_RE.search(url):
        return False                      # explicit search / results page
    if _SOFT_LISTING_RE.search(url) and not _JOB_ID_RE.search(url):
        return False                      # SEO category page with no job id
    return True


def _clean(text: str) -> str:
    if not text:
        return ""
    text = _TAG_RE.sub(" ", text)
    text = text.replace("&amp;", "&").replace("&nbsp;", " ").replace("&#39;", "'")
    return _WS_RE.sub(" ", text).strip()


def matches_filters(job: RawJob, query: str, location: str, keywords: List[str],
                    employment_type: str = "") -> bool:
    """Lightweight relevance filter applied after fetch.

    The query is matched against the job *title* (and company) so a search for
    "data scientist" doesn't match an unrelated role that merely mentions "data"
    in its description. Keywords are matched more broadly across the description.
    `employment_type` ("internship" | "fresher" | "job") filters by category.
    """
    if employment_type and employment_type not in ("any", ""):
        if infer_employment_type(job.title, job.employment_type).lower() != employment_type.lower():
            return False
    title_hay = f"{job.title} {job.company}".lower()
    full_hay = f"{title_hay} {job.description_snippet}".lower()
    if query:
        terms = [t.strip().lower() for t in re.split(r"[,\s]+", query) if t.strip()]
        # Require at least one query term to appear in the title/company.
        if terms and not any(t in title_hay for t in terms):
            return False
    if keywords:
        if not any(k.lower() in full_hay for k in keywords):
            return False
    if location:
        loc = location.lower()
        jl = job.location.lower()
        # "Remote" matches remote roles; India filters are India-aware (handle the
        # ", IN" country code + city synonyms providers emit); else substring match.
        if loc in ("remote",):
            if not job.remote and "remote" not in jl:
                return False
        elif india.is_india_filter(loc):
            if not india.india_location_matches(loc, jl, job.remote):
                return False
        elif loc not in jl and not (job.remote and not jl):
            # allow remote jobs through location filters too (they're location-agnostic)
            if not job.remote:
                return False
    return True
