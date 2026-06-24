"""Hybrid apply-mode registry — the single source of truth for how each source
is applied to.

Two application modes:
  • "auto_applied"          — Jobora can submit / assist on a genuine ATS apply
                              path (public ATS APIs). Greenhouse / Lever / Ashby /
                              SmartRecruiters / Workable.
  • "manual_link_provided"  — NO programmatic application path. Jobora discovers
                              the listing (via a licensed aggregator API or builds
                              a portal search link) and hands the user a direct
                              Apply URL to open in a new tab. It NEVER auto-submits
                              and NEVER scrapes login-gated / anti-bot portals.

LEGAL/ToS LINE (non-negotiable): Naukri, Indeed, LinkedIn, Foundit, Shine,
Internshala and Apna have no public application API; their robots.txt + ToS
disallow scraping their listing pages and they run anti-bot systems. So the
`*_search.py` modules here DO NOT scrape — they only build a public *search link*
to the portal (read-only deep link, no fetch, no login, no form submission).
Individual matched listings from those portals arrive only via licensed
aggregator APIs (JSearch / Adzuna), whose apply_url points back to the portal.
"""
from __future__ import annotations

# ATS sources with a genuine public application path → auto-apply supported.
AUTO_APPLY_SOURCES = {"Greenhouse", "Lever", "Ashby", "SmartRecruiters", "Workable"}

# Aggregator APIs: legitimate API data, but search→link only (no auto-submit).
SEARCH_LINK_SOURCES = {"Adzuna", "Jooble", "JSearch", "TheMuse", "RemoteOK",
                       "Jobicy", "Remotive", "Arbeitnow"}

# Portals with NO public API — link-out only, never scraped / never auto-applied.
MANUAL_PORTALS = {"Naukri", "Indeed", "LinkedIn", "Foundit", "Shine",
                  "Internshala", "Apna", "Unstop"}

AUTO_APPLIED = "auto_applied"
MANUAL_LINK = "manual_link_provided"


def auto_apply_supported(source: str) -> bool:
    """True if the source is an ATS with a genuine public apply path."""
    return (source or "") in AUTO_APPLY_SOURCES


def source_mode(source: str) -> str:
    """application_mode for a source: auto-capable ATS → auto_applied, else manual."""
    return AUTO_APPLIED if auto_apply_supported(source) else MANUAL_LINK


def portal_mode(source: str) -> str:
    """Coarse classification: 'auto' | 'search_link' | 'manual_portal'."""
    s = source or ""
    if s in AUTO_APPLY_SOURCES:
        return "auto"
    if s in MANUAL_PORTALS:
        return "manual_portal"
    return "search_link"


def application_mode(source: str, auto_submit: bool = False) -> str:
    """The per-application mode stored on the row.

    auto_applied only when the source is an auto-capable ATS AND the adapter can
    actually submit/assist; everything else is a manual link.
    """
    if auto_submit and auto_apply_supported(source):
        return AUTO_APPLIED
    return MANUAL_LINK


def portal_label(source: str) -> dict:
    """Badge metadata for the Portal Config UI."""
    mode = portal_mode(source)
    if mode == "auto":
        return {"source": source, "mode": mode, "auto_apply": True,
                "badge": "Auto-Apply Supported", "color": "green"}
    if mode == "manual_portal":
        return {"source": source, "mode": mode, "auto_apply": False,
                "badge": "Search Only — Manual Apply", "color": "blue",
                "note": "No public application API — Track & Apply on the portal only."}
    return {"source": source, "mode": mode, "auto_apply": False,
            "badge": "Search Only — Manual Apply", "color": "blue",
            "note": "API discovery; you apply on the employer/aggregator page."}


def all_portals() -> list:
    """Full portal config list (auto sources, aggregators, manual portals)."""
    ordered = (sorted(AUTO_APPLY_SOURCES) + sorted(SEARCH_LINK_SOURCES)
               + sorted(MANUAL_PORTALS))
    return [portal_label(s) for s in ordered]


def _slug(s: str) -> str:
    return "-".join((s or "").strip().lower().split())


# Extra no-API portals that don't have a dedicated *_search.py module. Read-only
# public search deep-links only — never fetched/scraped, never auto-submitted.
def _shine_link(q, loc):
    return f"https://www.shine.com/job-search/{_slug(q) or 'jobs'}-jobs-in-{_slug(loc) or 'india'}"


def _apna_link(q, loc):
    from urllib.parse import urlencode
    return "https://apna.co/jobs?" + urlencode({"q": q or "jobs"})


def internshala_search_link(query: str = "", location: str = "India",
                            employment_type: str = "") -> dict:
    """Build a direct deep-link to Internshala's OWN search-results page for the
    user's query — exactly like a 'Search on Google' link. We only CONSTRUCT a URL
    from the search terms; Jobora never fetches, reads, or parses Internshala (no
    scraping, no ToS issue). The user lands on Internshala's filtered results and
    browses/applies there themselves — this is NOT a specific job listing.

    Verified-working URL patterns (internshala.com):
      • internships → https://internshala.com/internships/keywords-{phrase}/
      • fresher jobs → https://internshala.com/jobs/keywords-{phrase}/
    Internshala is India-only, so the link is inherently India-scoped.
    """
    from urllib.parse import quote
    q = (query or "").strip()
    # Fresher roles live in Internshala's "jobs" section; otherwise "internships".
    section = "jobs" if (employment_type or "").lower() == "fresher" else "internships"
    if q:
        url = f"https://internshala.com/{section}/keywords-{quote(q.lower())}/"
        what = f"“{q}”"
    else:
        url = f"https://internshala.com/{section}/"
        what = "internships" if section == "internships" else "fresher jobs"
    return {
        "portal": "Internshala",
        "domain": "internshala.com",
        "auto_apply": False,
        "label": "Search on Internshala",
        "search_url": url,
        "note": (f"Opens Internshala's own search results for {what} — you browse and "
                 f"apply on Internshala (this is a search link, not a specific listing)."),
    }


def _internshala_link(q, loc):
    return internshala_search_link(q, loc)["search_url"]


def manual_portal_links(query: str = "", location: str = "India") -> list:
    """Read-only public SEARCH deep-links for the no-API portals (no scraping)."""
    from . import (naukri_search, indeed_search, linkedin_search, foundit_search,
                   unstop_search)
    out = [{"portal": m.NAME, "domain": m.DOMAIN, "auto_apply": False,
            "search_url": m.search_link(query, location)}
           for m in (naukri_search, indeed_search, linkedin_search, foundit_search,
                     unstop_search)]
    out += [
        {"portal": "Shine", "domain": "shine.com", "auto_apply": False,
         "search_url": _shine_link(query, location)},
        {"portal": "Internshala", "domain": "internshala.com", "auto_apply": False,
         "search_url": _internshala_link(query, location)},
        {"portal": "Apna", "domain": "apna.co", "auto_apply": False,
         "search_url": _apna_link(query, location)},
    ]
    return out
