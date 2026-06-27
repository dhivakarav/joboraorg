"""Real job discovery + AI-assisted application workflow.

Discovery: live from official provider APIs. Every job is scored against the
user's profile, salary is shown in INR, and the right platform adapter is
selected so the UI knows whether auto-apply is possible.

Apply workflow: prepare (map profile → form + screening questions) → user
reviews/edits → submit (records the application; performs the real browser
submission only for capable platforms in opt-in live mode, else marks
"Manual Apply Required").
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import notifications
from ..adapters import adapter_for, platform_capabilities
from ..adapters.greenhouse_fill import CORE_TEXT, fetch_fields
from ..adapters.greenhouse_production import apply as gh_apply
from ..adapters.greenhouse_production import parse_board_job, resolve_form_url
from ..adapters.runtime import live_ready
from ..config import settings
from ..database import get_db
from ..deps import get_approved_user
from ..jobs import aggregator
from ..jobs import india
from ..automation.matcher import score_job   # single resume↔job match engine
from ..jobs.eligibility import eligibility, early_signal, internships_only_default
from ..models import Application, JobFilter, Resume, User
from ..ratelimit import enforce
from ..schemas import (
    ApplyIntentIn,
    GreenhouseApplyIn,
    InternshalaApplyIn,
    JobOut,
    JobSearchOut,
    PlatformCredentialIn,
    PrepareIn,
    StatusUpdateIn,
    SubmitIn,
)
from .. import credentials as creds

from ..queue import enqueue as enqueue_submission  # noqa: E402
from ..services import cleanup_profile_resources as _cleanup_profile  # noqa: E402
from ..services import load_profile as _load_profile  # noqa: E402
from ..services import profile_complete as _profile_complete  # noqa: E402

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

EVIDENCE_ROOT = settings.UPLOAD_DIR / "evidence"


def _decorate(job: dict, profile: dict, applied_hashes: set, query: str = "") -> JobOut:
    """Attach match score, eligibility, platform capability, hybrid apply mode,
    and applied state. `query` is the user's explicit search so scoring/reasons
    reflect what they searched for."""
    from ..automation import portals
    match = score_job(job, profile, query=query)
    elig = eligibility(job, profile)
    adapter = adapter_for(job)
    src = job.get("source", "")
    return JobOut(
        **job,
        match_score=match["score"],
        match_reasons=match["reasons"],
        eligibility_score=elig["eligibility_score"],
        eligibility_tier=elig["eligibility_tier"],
        eligible=elig["eligible"],
        eligibility_reason=elig["eligibility_reason"],
        eligibility_reasons=elig["eligibility_reasons"],
        early_signal=early_signal(job),
        platform=adapter.platform,
        auto_submit=adapter.supports_auto_submit,
        manual_required=adapter.manual_only,
        application_mode=portals.source_mode(src),
        auto_apply_supported=portals.auto_apply_supported(src),
        applied=job["fingerprint"] in applied_hashes,
    )


def _rank_key(j: JobOut) -> float:
    """India-first, student-first ranking.

    Eligibility dominates and match breaks ties (as before); on top we add an
    India-location bonus (an explicit Indian hub outranks generic remote) and a
    priority-domain bonus (AI/ML, Data Science, SWE/SDE, Backend, Full Stack) so
    the roles an Indian student actually wants surface first.
    """
    base = j.eligibility_score * 0.55 + j.match_score * 0.30
    return base + india.india_bonus(j.location, j.remote) + india.domain_bonus(j.title)


@router.get("/sources")
def sources(user: User = Depends(get_approved_user)):
    return {"sources": aggregator.provider_status(), "platforms": platform_capabilities()}


@router.get("/portals")
def portals_config(q: str = Query(""), location: str = Query("India"),
                   user: User = Depends(get_approved_user)):
    """Portal Config: each portal labelled Auto-Apply Supported vs Search Only,
    plus read-only public SEARCH links for the no-API portals (Naukri/Indeed/
    LinkedIn/Foundit) — these never auto-submit and are never scraped."""
    from ..automation import portals as P
    return {"portals": P.all_portals(),
            "manual_search_links": P.manual_portal_links(q, location)}


@router.get("/internshala-link")
def internshala_link(q: str = Query(""), location: str = Query("India"),
                     employment_type: str = Query(""),
                     user: User = Depends(get_approved_user)):
    """The 'Search on Internshala' deep-link for a query. A constructed URL only —
    Jobora never fetches/parses Internshala. Used by Matched Jobs (Find Jobs gets
    the same link inline in its search response)."""
    from ..automation import portals
    return portals.internshala_search_link(q, location, employment_type)


@router.get("/analytics")
async def discovery_analytics(
    refresh: bool = Query(False, description="bypass cache + pull freshest postings"),
    user: User = Depends(get_approved_user),
    db: Session = Depends(get_db),
):
    """Job Discovery Analytics: counts from the same aggregator.search() call the
    scanner uses, not from the Application table.

    Root cause of the previous bug (a5dc986): the endpoint was reading the Application
    table (cumulative tracking history) instead of the aggregator results (what
    providers actually discovered this scan). When all matched jobs were already
    tracked from a prior scan, 0 new Application rows were added and the cards never
    changed — even though the providers returned 169 fresh openings.

    Fix: call aggregator.search() with the user's own profile parameters (identical
    to what the engine does) and use_cache=True so it hits the scanner's warm cache
    with zero extra network calls. ?refresh=true forces a live re-fetch.
    """
    from datetime import datetime, timezone
    from ..jobs.base import infer_employment_type
    from ..jobs.matching import is_ai_ml

    # ── 1. Load the user's scan parameters (mirrors engine._load_context) ──────
    profile = _load_profile(db, user, materialize=False)
    filt = db.query(JobFilter).filter_by(user_id=user.id).first()
    roles = profile.get("roles", [])
    keywords = profile.get("keywords", [])
    locations = profile.get("locations", [])
    min_match = (filt.min_match_score if (filt and filt.min_match_score is not None) else 50) or 0
    # Build the search query the same way the engine does.
    query = " ".join(roles[:3]) or user.job_title or "software engineer"
    location = locations[0] if locations else ""

    # ── 2. Fetch from aggregator using the user's real params ─────────────────
    # use_cache=True → hits the scanner's warm cache instantly (no extra API calls).
    # ?refresh=true  → forces a live re-fetch from all providers.
    jobs = await aggregator.search(
        query=query, location=location, keywords=keywords,
        limit=300, use_cache=not refresh,
    )

    # ── 3. Score and count categories (same logic as the scanner engine) ───────
    internships = 0
    freshers = 0
    ai_ml_count = 0
    matched = 0
    by_source: dict = {}

    for j in jobs:
        title = j.get("title", "")
        snippet = j.get("description_snippet", "")
        source = j.get("source", "")

        et = j.get("employment_type") or infer_employment_type(title)
        if et == "internship":
            internships += 1
        elif et == "fresher":
            freshers += 1
        if is_ai_ml(title, snippet):
            ai_ml_count += 1
        if score_job(j, profile)["score"] >= min_match:
            matched += 1
        if source:
            by_source[source] = by_source.get(source, 0) + 1

    total = len(jobs)
    coverage_pct = round(100 * matched / total) if total else 0

    # ── 4. Provider connectivity ───────────────────────────────────────────────
    status = aggregator.provider_status()
    live = [s for s in status if s.get("status") == "Connected"]

    return {
        "jobs_discovered": total,
        "internships": internships,
        "freshers": freshers,
        "ai_ml": ai_ml_count,
        "coverage_percentage": coverage_pct,
        "live_providers": len(live),
        "total_providers": len(status),
        "last_sync": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds"),
        "by_source": by_source,
        "sources": status,
    }


@router.get("", response_model=JobSearchOut)
async def search_jobs(
    q: str = Query(""),
    location: str = Query(""),
    employment_type: str = Query("", description="internship | fresher | job | any"),
    limit: int = Query(60, ge=1, le=300),
    refresh: bool = Query(False),
    include_ineligible: bool = Query(False, description="include roles flagged not-eligible (senior/PhD/visa)"),
    internships_only: Optional[bool] = Query(None, description="hard filter: only intern/new-grad/fresher roles (defaults ON for students/freshers)"),
    company: str = Query("", description="filter to a company (case-insensitive substring)"),
    min_salary: int = Query(0, ge=0, description="minimum ANNUAL salary in INR (unknown-salary roles are kept)"),
    duration: str = Query("", description="internship duration bucket, e.g. '3' or '6' (months)"),
    remote: bool = Query(False, description="keep only remote roles (combines with location, e.g. location=India&remote=true)"),
    sources: str = Query("", description="comma-separated source names to include (e.g. Greenhouse,Lever,Jooble)"),
    min_match: Optional[int] = Query(None, ge=0, le=100, description="min resume match score (defaults to the user's Filters setting)"),
    broad: bool = Query(False, description="discovery-wide: skip the forced default keyword + keyword hard-filter (used by Matched Jobs), rank by match score"),
    user: User = Depends(get_approved_user),
    db: Session = Depends(get_db),
):
    enforce("search", str(user.id), settings.RL_SEARCH_PER_MIN, 60)
    # Search only needs the text fields of the profile (skills, keywords, etc.)
    # for scoring — no resume file is read or uploaded here, so skip materialization.
    profile = _load_profile(db, user, materialize=False)
    keywords = profile["keywords"]
    # The query the USER actually typed (before we default it from their profile).
    # Drives query-relevant scoring + a strict title filter so e.g. "data engineer"
    # returns Data Engineer roles, not profile-matched "Software Engineer" leftovers.
    explicit_query = (q or "").strip()
    # Default the location from the profile when none is given.
    if not location and profile["locations"]:
        location = profile["locations"][0]
    # Keyword default: only apply a role/title keyword for the general tabs. For the
    # internship / fresher tabs we deliberately keep the query BROAD (empty) so the
    # tab surfaces ALL intern/fresher roles, not just ones matching a default role
    # string like "software engineer" — that default was silently killing India
    # internship coverage.
    early_tab = employment_type in ("internship", "fresher")
    if not q and not early_tab and not broad:
        if profile["roles"]:
            q = " ".join(profile["roles"][:3])
        if not q:
            q = user.job_title or "software engineer"

    # On the internship / fresher tabs, don't let profile keywords HARD-filter the
    # pool — that shrinks early-career coverage. Match scoring still ranks the most
    # relevant intern/fresher roles to the top; we just stop excluding the rest.
    search_keywords = [] if (early_tab or broad) else keywords
    # Pull a much larger pool from the aggregator when a downstream filter will
    # narrow it: a specific source filter, OR an explicit user query (whose strict
    # title-relevance filter below would otherwise be starved if the relevant roles
    # were trimmed off by the global verified-first/recency cut first).
    agg_limit = max(limit, 400) if (sources or explicit_query) else limit
    jobs = await aggregator.search(
        query=q, location=location, keywords=search_keywords, limit=agg_limit,
        use_cache=not refresh, employment_type=employment_type,
        # Refresh = fresh live calls + newest-posted-first ordering.
        recent=refresh,
    )

    # Internshala honesty gate: with no AUTHORIZED feed (Disabled / Mock Mode), do
    # NOT surface Internshala listings in real search results — sample/mock data
    # must never masquerade as real openings. The sources panel explains the status.
    from ..jobs.providers.internshala import InternshalaProvider
    if not InternshalaProvider().authorized():
        jobs = [j for j in jobs if (j.get("source") or "").lower() != "internshala"]

    # Source filter: keep only the selected sources. Matches by provider name OR
    # the apply-URL domain — so a manual portal toggle (e.g. "Unstop"/"Naukri")
    # also keeps aggregator rows whose apply_url points to that portal.
    if sources:
        wanted = {s.strip().lower() for s in sources.split(",") if s.strip()}
        if wanted:
            def _src_match(j):
                src = (j.get("source") or "").lower()
                dom = (j.get("source_domain") or j.get("apply_url") or "").lower()
                return src in wanted or any(w in src or w in dom for w in wanted)
            jobs = [j for j in jobs if _src_match(j)]

    # Every surfaced row must link to a SPECIFIC job page (not a search/homepage).
    from ..jobs.base import is_specific_job_url
    jobs = [j for j in jobs if is_specific_job_url(j.get("apply_url", ""))]

    # STRICT QUERY RELEVANCE: when the user typed a role (e.g. "data engineer"),
    # every result's TITLE must contain ALL meaningful query terms — so a shared
    # generic word ("engineer") can't pull in off-target roles ("Software
    # Engineer"). The aggregator's pre-filter only requires ONE term, which is too
    # loose for a precise role search. Skip on the internship/fresher tabs and broad
    # (Matched Jobs) mode, where the query is intentionally kept wide.
    if explicit_query and not early_tab and not broad:
        import re as _re
        terms = [t for t in _re.split(r"[,\s]+", explicit_query.lower()) if len(t) >= 2]
        if terms:
            def _title_relevant(j):
                title = (j.get("title") or "").lower()
                return all(t in title for t in terms)
            jobs = [j for j in jobs if _title_relevant(j)]

    applied_hashes = {
        row[0] for row in db.query(Application.job_url_hash).filter_by(user_id=user.id).all()
    }
    items = [_decorate(j, profile, applied_hashes, query=explicit_query) for j in jobs]

    # Strict eligibility filtering is ON FOR EVERYONE (not a paywalled feature):
    # "Not Recommended" roles (senior/staff/principal/lead/manager/director/
    # architect/PhD/Master's-required/3+ yrs) are hidden by default for early-career
    # users. Eligibility-first, student-first ranking; match score breaks ties.
    hidden = sum(1 for j in items if not j.eligible)
    if not include_ineligible:
        items = [j for j in items if j.eligible]
    else:
        hidden = 0

    # Resume match-score threshold (hybrid model): only show jobs above the user's
    # configurable minimum (Filters page, default 50). Override per-request via
    # ?min_match=. 0 disables it.
    if min_match is None:
        mm = db.query(JobFilter.min_match_score).filter_by(user_id=user.id).scalar()
        min_match = mm if mm is not None else 50
    filtered_low_match = 0
    if min_match:
        before = len(items)
        items = [j for j in items if j.match_score >= min_match]
        filtered_low_match = before - len(items)

    # Internships-&-new-grad hard filter: keep only roles carrying an explicit
    # early-career signal (Intern/New Grad/Graduate Program/University Graduate/
    # Campus/Fresher/Entry Level/Associate Engineer). Generic "Software Engineer"
    # and any senior title are dropped. Defaults ON for students/freshers; the user
    # can disable it (?internships_only=false).
    io = internships_only_default(profile) if internships_only is None else internships_only
    filtered_generic = 0
    # Skip this hard filter on the internship/fresher tabs — `employment_type` is
    # already the early-career filter there, and the stricter `early_signal` gate
    # wrongly drops valid fresher roles (e.g. "Operations Associate"), zeroing out
    # fresher coverage.
    if io and not early_tab:
        kept = [j for j in items if j.early_signal]
        filtered_generic = len(items) - len(kept)
        items = kept

    # Discovery filters (company / minimum INR salary / internship duration).
    # Applied after eligibility so counts above stay meaningful. Unknown salary
    # and unknown duration are kept — never filtered out — since most internships
    # don't publish either.
    if company:
        items = [j for j in items if india.company_match(j.company, company)]
    if min_salary:
        items = [j for j in items if india.passes_salary(j.salary_inr, min_salary)]
    if duration:
        items = [j for j in items if india.duration_match(j.duration, duration)]
    # Remote tab: keep only remote roles, applied ON TOP of the location filter so
    # "India + Remote" yields remote India roles (never global remote that bypasses
    # the chosen location).
    if remote:
        items = [j for j in items if j.remote]
        # India + Remote is India-first: show only India-tagged / Remote-India roles
        # and exclude generic worldwide-remote postings (location "Remote"/blank that
        # carry no India tag) which the location filter otherwise lets through.
        if location and india.is_india_filter(location):
            items = [j for j in items if india.is_india_location(j.location)]

    # When the user searched a SPECIFIC non-India location (e.g. Dubai, Singapore),
    # jobs actually IN that location must rank first — otherwise verified global/
    # remote jobs that merely passed the filter bury the location-matched ones
    # (this is why Dubai showed 0 local jobs even though they were fetched).
    loc_q = (location or "").strip().lower()
    location_specified = bool(loc_q) and not india.is_india_filter(loc_q)

    def _loc_match(j):
        return 0 if (location_specified and loc_q in (j.location or "").lower()) else 1

    # India-first, EARLY-CAREER-first tiered ordering (maximises India internship/
    # fresher coverage at the top): Tier 1 India intern/fresher/new-grad on-site →
    # Tier 2 remote-India intern/fresher → India (any) → global remote → global
    # on-site. Within a tier the existing relevance order (_rank_key) is preserved.
    items.sort(key=lambda j: (
        _loc_match(j),   # exact searched-location matches first (non-India searches)
        india.india_internship_tier(j.location, j.remote, j.employment_type,
                                    bool(j.early_signal)),
        -_rank_key(j)))

    # Respect the requested display limit. We intentionally pull a LARGER pool from
    # the aggregator (agg_limit) so source/query filters aren't starved, but only
    # the top `limit` ranked results are returned to the UI.
    items = items[:limit]

    from ..jobs import coverage
    insh = coverage.internshala_breakdown(items)

    # "Search on Internshala" deep-link — always available (a constructed URL, not a
    # fetched listing), shown when the context is India + intern/fresher. Internshala
    # is India-only, so a blank location (India-first default) also qualifies; an
    # explicit non-India location (Dubai/Singapore) does not.
    from ..automation import portals
    india_ctx = (not location) or india.is_india_filter(location)
    intern_fresher_ctx = early_tab or io or employment_type in ("internship", "fresher")
    # Explicit fresher tab → Internshala "jobs" section; internship tab or the
    # generic intern/fresher (internships_only) default → "internships" section.
    internshala_search = (
        portals.internshala_search_link(q, location or "India", employment_type)
        if (india_ctx and intern_fresher_ctx) else {})

    from .. import analytics
    analytics.capture(analytics.JOB_SEARCH, user.id,
                      {"q": q, "location": location, "results": len(items),
                       "internships_only": io, "company": company,
                       "min_salary": min_salary, "duration": duration, "remote": remote,
                       "internshala": insh})

    return JobSearchOut(items=items, total=len(items), sources=aggregator.provider_status(),
                        hidden_ineligible=hidden, internships_only=io,
                        filtered_generic=filtered_generic, filtered_low_match=filtered_low_match,
                        min_match=min_match or 0, internshala_coverage=insh,
                        internshala_search=internshala_search)


@router.post("/prepare")
def prepare_application(
    job: PrepareIn,
    user: User = Depends(get_approved_user),
    db: Session = Depends(get_db),
):
    """Map the user's profile onto the platform's application form.

    Returns the prefilled package + screening questions + capability so the
    frontend can show a review-and-approve screen.
    """
    profile = _load_profile(db, user)
    try:
        if not profile["resume_path"]:
            raise HTTPException(status_code=400, detail="Upload your resume first so we can prepare the application")

        job_dict = job.model_dump()
        adapter = adapter_for(job_dict)
        package = adapter.build_package(profile, job_dict, profile["resume_path"])
        match = score_job(job_dict, profile)
        from .. import analytics
        analytics.capture(analytics.JOB_CLICK, user.id,
                          {"platform": adapter.platform, "company": job_dict.get("company", "")})
        return {
            "platform": adapter.platform,
            "auto_submit": adapter.supports_auto_submit,
            "manual_required": adapter.manual_only,
            "match_score": match["score"],
            "match_reasons": match["reasons"],
            "package": package.to_dict(),
        }
    finally:
        _cleanup_profile(profile)


@router.post("/submit")
async def submit_application(
    data: SubmitIn,
    user: User = Depends(get_approved_user),
    db: Session = Depends(get_db),
):
    """Record (and, where possible, auto-submit) an application after approval."""
    if not data.approved:
        raise HTTPException(status_code=400, detail="Application must be approved before submitting")

    job = data.job.model_dump()
    adapter = adapter_for(job)
    profile = _load_profile(db, user)
    try:
        package = adapter.build_package(profile, job, profile["resume_path"])

        # Perform the platform action (manual-only → no-op; capable → live/opt-in).
        result = await adapter.submit(package, data.answers or {})

        if result.get("submitted"):
            status, sub = "Submitted", "Submitted"
        elif result.get("manual_required"):
            status, sub = "Pending", "Manual Apply"
        elif result.get("failed"):
            status, sub = "Pending", "Failed"
        else:
            status, sub = "Tracked", "Draft"

        match = score_job(job, profile)
        existing = (
            db.query(Application).filter_by(user_id=user.id, job_url_hash=job["fingerprint"]).first()
        )
        if existing:
            existing.status = status
            existing.submission_status = sub
            existing.platform = adapter.platform
            existing.manual_required = adapter.manual_only
            existing.match_score = match["score"]
            existing.salary_inr = job.get("salary_inr", "")
            db.commit()
            app = existing
        else:
            app = Application(
                user_id=user.id,
                portal=job["source"],
                source=job["source"],
                platform=adapter.platform,
                job_title=job["title"],
                company=job["company"],
                location=job.get("location", ""),
                salary=job.get("salary", ""),
                salary_inr=job.get("salary_inr", ""),
                apply_url=job["apply_url"],
                verified=job.get("verified", False),
                match_score=match["score"],
                manual_required=adapter.manual_only,
                job_url_hash=job["fingerprint"],
                status=status,
                submission_status=sub,
            )
            db.add(app)
            db.commit()
            db.refresh(app)

        notifications.application_recorded(user.email, user.full_name, job["title"],
                                           job["company"], status)

        from .. import analytics
        analytics.capture(analytics.APPLICATION_STARTED, user.id,
                          {"platform": adapter.platform, "company": job.get("company", "")})
        if result.get("submitted"):
            analytics.capture(analytics.APPLICATION_SUBMITTED, user.id,
                              {"platform": adapter.platform})
        elif result.get("manual_required"):
            analytics.capture(analytics.MANUAL_APPLY, user.id, {"platform": adapter.platform})

        return {
            "message": result.get("message", "Application recorded"),
            "status": status,
            "manual_required": adapter.manual_only,
            "apply_url": job["apply_url"],
            "application_id": app.id,
        }
    finally:
        _cleanup_profile(profile)


@router.post("/apply")
def apply_to_job(
    data: ApplyIntentIn,
    user: User = Depends(get_approved_user),
    db: Session = Depends(get_db),
):
    """Lightweight 'Save' / quick-track without the full workflow.

    No submission happens here, so the only honest outcomes are 'Saved' (Draft)
    or 'Tracked' (monitored). A client sending the retired 'Applied' is coerced to
    'Tracked' — clicking Apply merely starts tracking; it never marks submitted.
    """
    if data.status not in ("Applied", "Saved", "Tracked"):
        raise HTTPException(status_code=400, detail="Invalid status")
    # Canonical mapping: Applied -> Tracked, Saved -> Saved.
    lifecycle = "Saved" if data.status == "Saved" else "Tracked"
    sub = "Draft"  # nothing submitted via this endpoint
    existing = (
        db.query(Application).filter_by(user_id=user.id, job_url_hash=data.fingerprint).first()
    )
    if existing:
        if existing.status == "Saved" and lifecycle == "Tracked":
            existing.status = "Tracked"
            db.commit()
        return {"message": "Already tracked", "apply_url": existing.apply_url,
                "status": existing.status, "display_status": existing.display_status}

    app = Application(
        user_id=user.id, portal=data.source, source=data.source, platform=data.platform,
        job_title=data.title, company=data.company, location=data.location,
        salary=data.salary, salary_inr=data.salary_inr, deadline=data.deadline,
        apply_url=data.apply_url, verified=data.verified, match_score=data.match_score,
        manual_required=data.manual_required, job_url_hash=data.fingerprint,
        status=lifecycle, submission_status=sub,
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    from .. import analytics
    analytics.capture(analytics.TRACKED_JOB, user.id,
                      {"platform": data.platform, "company": data.company})
    return {"message": f"Job {lifecycle.lower()}", "apply_url": data.apply_url,
            "status": lifecycle, "display_status": app.display_status}


@router.post("/greenhouse/form")
def greenhouse_form(
    data: GreenhouseApplyIn,
    user: User = Depends(get_approved_user),
    db: Session = Depends(get_db),
):
    """READ-ONLY: the Greenhouse posting's required screening questions + the
    profile prefill, so the submit wizard can collect truthful answers BEFORE the
    user confirms a real submission. Uses the public Board API (no browser, no
    submit, no DB write)."""
    # Rate-limited: each call hits the external Greenhouse Board API. Shares the
    # search bucket (30/min per user) so one spammer can't flood an upstream API.
    enforce("search", str(user.id), settings.RL_SEARCH_PER_MIN, 60)
    if data.source.lower() != "greenhouse":
        raise HTTPException(status_code=400, detail="This endpoint only handles Greenhouse jobs")
    bj = parse_board_job(data.model_dump())
    if not bj:
        raise HTTPException(status_code=400, detail="Could not resolve the Greenhouse board/job id")
    try:
        title, fields = fetch_fields(bj[0], bj[1])
    except Exception:
        raise HTTPException(status_code=502, detail="Could not load the Greenhouse application form")

    # greenhouse_form only needs profile identity fields + filename (not the PDF).
    profile = _load_profile(db, user, materialize=False)
    ok, missing = _profile_complete(profile)
    skip = CORE_TEXT | {"resume", "resume_text", "cover_letter", "cover_letter_text"}

    def q(f):
        return {"name": f.name, "label": f.label, "type": f.type, "required": f.required,
                "values": [{"label": l, "value": v} for l, v in (f.values or [])]}

    qs = [q(f) for f in fields if f.name and f.name not in skip]
    # For the form preview, show the stored filename from the DB path, not the tmp path.
    from ..models import Resume as _Resume
    _res = db.query(_Resume).filter_by(user_id=user.id).first()
    rf = (_res.file_path.split("/")[-1] if _res and _res.file_path else "")
    return {
        "title": title or data.title,
        "company": data.company,
        "profile_complete": ok,
        "missing_profile": missing,
        "prefill": {"name": profile.get("name", ""), "email": profile.get("email", ""),
                    "phone": profile.get("phone", ""), "resume_filename": rf},
        "required_questions": [x for x in qs if x["required"]],
        "optional_questions": [x for x in qs if not x["required"]],
    }


@router.post("/greenhouse/apply")
async def greenhouse_apply(
    data: GreenhouseApplyIn,
    user: User = Depends(get_approved_user),
    db: Session = Depends(get_db),
):
    """Production: submit ONE real Greenhouse application for the signed-in user.

    Hard gates (all required): explicit approval, a real uploaded resume, a
    complete profile, the job is a Greenhouse posting, and live mode is ready.
    Never fabricates data — only the user's profile + their reviewed answers.
    """
    # Rate limit: per-user burst + daily cap (browser-launching endpoint).
    enforce("gh_apply_burst", str(user.id), settings.RL_APPLY_BURST_PER_MIN, 60)
    enforce("gh_apply_day", str(user.id), settings.RL_APPLY_PER_DAY, 86400)

    # Gate 1 — explicit click/approval.
    if not data.approved:
        raise HTTPException(status_code=400, detail="You must explicitly approve before submitting")

    # Gate 2 — must be a Greenhouse job we can reach.
    job = data.model_dump()
    if data.source.lower() != "greenhouse":
        raise HTTPException(status_code=400, detail="This endpoint only handles Greenhouse jobs")
    form_url = resolve_form_url(job)
    if not form_url:
        raise HTTPException(status_code=400, detail="Could not resolve the Greenhouse application form URL")

    # Gate 3 — real resume + complete profile.
    # The queue worker materializes its own copy; here we only validate identity
    # fields and confirm a resume is stored (no temp file needed at this stage).
    profile = _load_profile(db, user, materialize=False)
    identity_missing = [k for k in ("name", "email", "phone")
                        if not (profile.get(k) or "").strip()]
    if identity_missing:
        raise HTTPException(status_code=400,
                            detail=f"Complete your profile before applying. Missing: {', '.join(identity_missing)}")
    from ..models import Resume as _Resume
    if not db.query(_Resume).filter_by(user_id=user.id).first():
        raise HTTPException(status_code=400, detail="Upload a resume before applying")

    # Upsert the application row and ENQUEUE it. The browser submission runs in a
    # background worker (concurrency-capped, retried) — never inline in this
    # request, which returns immediately. (H1)
    app = db.query(Application).filter_by(user_id=user.id, job_url_hash=data.fingerprint).first()
    if not app:
        app = Application(user_id=user.id, job_url_hash=data.fingerprint)
        db.add(app)
    app.portal = data.source
    app.source = data.source
    app.platform = "Greenhouse"
    app.job_title = data.title
    app.company = data.company
    app.location = data.location
    app.salary = data.salary
    app.salary_inr = data.salary_inr
    app.apply_url = data.apply_url
    app.verified = data.verified
    app.manual_required = False
    app.submission_status = "Queued"
    app.submission_attempts = 0
    app.submission_payload = json.dumps({
        "answers": data.answers or {},
        "external_id": data.external_id,
        "form_url": form_url,
    })
    db.commit()
    db.refresh(app)

    backend = enqueue_submission(app.id)
    return {
        "submission_status": "Queued",
        "application_id": app.id,
        "queue_backend": backend,
        "message": "Application queued — processing in the background. Track status in your Activity Log.",
    }


# ----------------------------------------------------------------------------
# Internshala live auto-submission (Option B) — credential-gated, opt-in.
# ----------------------------------------------------------------------------
@router.get("/internshala/credentials")
def internshala_credentials_status(user: User = Depends(get_approved_user),
                                   db: Session = Depends(get_db)):
    """Whether the user has Internshala credentials on file. Never returns secrets."""
    ready, reason = live_ready()
    return {"has_credentials": creds.has_credentials(db, user.id, "Internshala"),
            "live_ready": ready, "live_reason": reason}


@router.post("/internshala/credentials")
def set_internshala_credentials(data: PlatformCredentialIn,
                                user: User = Depends(get_approved_user),
                                db: Session = Depends(get_db)):
    """Store the user's OWN Internshala login (encrypted at rest)."""
    if not data.username or not data.password:
        raise HTTPException(status_code=400, detail="username and password are required")
    creds.set_credentials(db, user.id, "Internshala", data.username, data.password)
    return {"message": "Internshala credentials saved (encrypted).", "has_credentials": True}


@router.delete("/internshala/credentials")
def delete_internshala_credentials(user: User = Depends(get_approved_user),
                                   db: Session = Depends(get_db)):
    removed = creds.delete_credentials(db, user.id, "Internshala")
    return {"message": "Removed" if removed else "Nothing to remove", "has_credentials": False}


@router.post("/internshala/apply")
async def internshala_apply(data: InternshalaApplyIn,
                            user: User = Depends(get_approved_user),
                            db: Session = Depends(get_db)):
    """Production: submit ONE real Internshala application for the signed-in user.

    Hard gates (all required): explicit approval, live mode ready, the user's own
    Internshala credentials on file, a user-reviewed cover letter, a real resume,
    and an Internshala-sourced job. Never fabricates data; runs under the user's
    account only. The browser submission runs in the background worker.
    """
    # Per-user burst + daily cap (browser-launching endpoint).
    enforce("ish_apply_burst", str(user.id), settings.RL_APPLY_BURST_PER_MIN, 60)
    enforce("ish_apply_day", str(user.id), settings.RL_APPLY_PER_DAY, 86400)

    # Gate 1 — explicit approval.
    if not data.approved:
        raise HTTPException(status_code=400, detail="You must explicitly approve before submitting")

    # Gate 2 — must be an Internshala job.
    job = data.model_dump()
    adapter = adapter_for(job)
    if adapter.platform != "Internshala":
        raise HTTPException(status_code=400, detail="This endpoint only handles Internshala jobs")

    # Gate 2b — an AUTHORIZED feed must exist. Mock Mode / Disabled cannot auto-apply:
    # the listings aren't real, and unattended applies to real Internshala aren't
    # permitted without authorization.
    from ..jobs.providers.internshala import InternshalaProvider
    if not InternshalaProvider().authorized():
        raise HTTPException(status_code=403,
                            detail="Internshala auto-apply requires an authorized feed "
                                   "(currently Mock Mode / Disabled).")

    # Gate 3 — live mode ready (JOBORA_LIVE=1 + Chromium installed).
    ready, reason = live_ready()
    if not ready:
        raise HTTPException(status_code=409, detail=f"Live submission unavailable: {reason}")

    # Gate 4 — user's own credentials on file.
    if not creds.has_credentials(db, user.id, "Internshala"):
        raise HTTPException(status_code=400,
                            detail="Add your Internshala login first (Settings → Internshala credentials).")

    # Gate 5 — user-reviewed cover letter (we never write it for them).
    if not (data.cover_letter or "").strip():
        raise HTTPException(status_code=400,
                            detail="Provide a cover letter you've reviewed — Internshala requires one.")

    # Gate 6 — real resume exists in storage (worker materializes its own copy).
    from ..models import Resume as _Resume2
    if not db.query(_Resume2).filter_by(user_id=user.id).first():
        raise HTTPException(status_code=400, detail="Upload a resume before applying")

    # Upsert + enqueue. Browser submission runs in the background worker.
    app = db.query(Application).filter_by(user_id=user.id, job_url_hash=data.fingerprint).first()
    if not app:
        app = Application(user_id=user.id, job_url_hash=data.fingerprint)
        db.add(app)
    app.portal = data.source
    app.source = data.source
    app.platform = "Internshala"
    app.job_title = data.title
    app.company = data.company
    app.location = data.location
    app.salary = data.salary
    app.salary_inr = data.salary_inr
    app.apply_url = data.apply_url
    app.verified = data.verified
    app.manual_required = False
    app.submission_status = "Queued"
    app.submission_attempts = 0
    app.submission_payload = json.dumps({
        "answers": {**(data.answers or {}), "cover_letter": data.cover_letter},
    })
    db.commit()
    db.refresh(app)

    backend = enqueue_submission(app.id)
    return {
        "submission_status": "Queued",
        "application_id": app.id,
        "queue_backend": backend,
        "message": "Internshala application queued — submitting under your account in the background.",
    }


@router.post("/refresh")
def refresh_cache(user: User = Depends(get_approved_user)):
    aggregator.clear_cache()
    return {"message": "Job cache cleared — next search fetches fresh listings"}


# ── Extension endpoints (used by the Jobora LinkedIn browser extension) ────────
# Pure computation / AI helpers — no DB writes — so the extension can score and
# analyse a job before (or without) saving it.

from pydantic import BaseModel as _BaseModel  # noqa: E402


class _ExtJobIn(_BaseModel):
    """Minimal job payload sent by the browser extension."""
    title: str
    company: str = ""
    location: str = ""
    description_snippet: str = ""
    employment_type: str = ""
    experience_level: str = ""
    salary: str = ""
    source: str = "LinkedIn"
    url: str = ""
    skills: List[str] = []


@router.post("/score")
def score_extension_job(
    job: _ExtJobIn,
    user: User = Depends(get_approved_user),
    db: Session = Depends(get_db),
):
    """Score a single job (sent by the browser extension) against the user's
    resume. Returns match score, reasons, missing skills, and eligibility tier.
    Pure computation — no DB write.
    """
    profile = _load_profile(db, user, materialize=False)
    job_dict = {
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "description_snippet": job.description_snippet,
        "employment_type": job.employment_type,
        "salary": job.salary,
        "source": job.source,
        "apply_url": job.url,
        "remote": "remote" in (job.location or "").lower(),
    }
    match = score_job(job_dict, profile)
    elig = eligibility(job_dict, profile)

    # Missing skills = resume skills not mentioned in title or description.
    resume_skills = profile.get("skills", [])
    job_text = f"{job.title} {job.description_snippet}".lower()
    missing = [s for s in resume_skills if s.lower() not in job_text]

    # Check if already tracked.
    import hashlib
    basis = f"{job.source}|{job.company}|{job.title}|{job.url}"
    fingerprint = hashlib.sha256(basis.lower().encode()).hexdigest()[:32]
    already_saved = db.query(Application.id).filter_by(
        user_id=user.id, job_url_hash=fingerprint).first() is not None

    return {
        "fingerprint": fingerprint,
        "match_score": match["score"],
        "match_reasons": match["reasons"],
        "missing_skills": missing[:12],
        "eligibility_score": elig["eligibility_score"],
        "eligibility_tier": elig["eligibility_tier"],
        "eligible": elig["eligible"],
        "eligibility_reason": elig["eligibility_reason"],
        "already_saved": already_saved,
    }


@router.post("/ai-tips")
def ai_resume_tips(
    job: _ExtJobIn,
    user: User = Depends(get_approved_user),
    db: Session = Depends(get_db),
):
    """Generate targeted resume improvement tips for a specific job using Claude.
    Falls back to a heuristic list when ANTHROPIC_API_KEY is unset.
    """
    from ..ai.client import available, generate_text
    from ..models import Resume as _Resume

    profile = _load_profile(db, user, materialize=False)
    resume_skills = profile.get("skills", [])
    job_text = f"{job.title} {job.description_snippet}".lower()
    missing = [s for s in resume_skills if s.lower() not in job_text]

    if available():
        res_row = db.query(_Resume).filter_by(user_id=user.id).first()
        resume_text = ""
        if res_row and res_row.raw_text:
            from ..security import decrypt_value
            try:
                resume_text = decrypt_value(res_row.raw_text) if res_row.raw_text else ""
            except Exception:
                resume_text = res_row.raw_text or ""

        task = (
            f"Job: {job.title} at {job.company} ({job.location})\n"
            f"Description: {job.description_snippet[:800]}\n\n"
            "Give 3 specific, actionable resume improvement tips for this exact role. "
            "Be concise — one sentence per tip. Format as a numbered list."
        )
        tips = generate_text(task, resume_text=resume_text, max_tokens=512)
        if tips:
            return {"tips": tips, "ai": True}

    # Heuristic fallback.
    tips_list = []
    if missing:
        tips_list.append(f"Add these skills to your resume: {', '.join(missing[:5])}.")
    if job.employment_type == "internship":
        tips_list.append("Highlight coursework, projects, and hackathons relevant to this internship.")
    tips_list.append(
        f"Tailor your summary to mention {job.company} and the specific role '{job.title}'."
    )
    return {"tips": "\n".join(f"{i+1}. {t}" for i, t in enumerate(tips_list)), "ai": False}


@router.post("/cover-letter")
def generate_cover_letter(
    job: _ExtJobIn,
    user: User = Depends(get_approved_user),
    db: Session = Depends(get_db),
):
    """Generate a tailored cover letter for the given job using Claude.
    Falls back to a structured template when AI is unavailable.
    """
    from ..ai.client import available, generate_text
    from ..models import Resume as _Resume

    profile = _load_profile(db, user, materialize=False)

    if available():
        res_row = db.query(_Resume).filter_by(user_id=user.id).first()
        resume_text = ""
        if res_row and res_row.raw_text:
            from ..security import decrypt_value
            try:
                resume_text = decrypt_value(res_row.raw_text) if res_row.raw_text else ""
            except Exception:
                resume_text = res_row.raw_text or ""

        task = (
            f"Write a concise, genuine cover letter (3 short paragraphs, ≤200 words) "
            f"for:\n  Role: {job.title}\n  Company: {job.company}\n"
            f"  Location: {job.location}\n"
            f"  Job description excerpt: {job.description_snippet[:600]}\n\n"
            "Do NOT invent facts. Base everything on the candidate's actual resume. "
            "Do NOT include 'Dear Hiring Manager' or a date — just the body."
        )
        letter = generate_text(task, resume_text=resume_text, max_tokens=600)
        if letter:
            return {"cover_letter": letter, "ai": True}

    # Template fallback.
    name = profile.get("name") or user.full_name
    skills_preview = ", ".join((profile.get("skills") or [])[:4])
    letter = (
        f"I am excited to apply for the {job.title} position at {job.company}. "
        f"With my background in {skills_preview or 'software development'}, "
        f"I am confident I can contribute meaningfully to your team.\n\n"
        f"My experience aligns well with the requirements of this role, and I am "
        f"particularly drawn to {job.company}'s mission and the opportunity to "
        f"work in {job.location or 'this field'}.\n\n"
        f"I would welcome the opportunity to discuss how my skills can benefit your team. "
        f"Thank you for considering my application.\n\nSincerely,\n{name}"
    )
    return {"cover_letter": letter, "ai": False}


@router.post("/ai-summary")
def ai_match_summary(
    job: _ExtJobIn,
    user: User = Depends(get_approved_user),
    db: Session = Depends(get_db),
):
    """Generate a 2-3 sentence plain-English summary of how this job matches the
    user's profile — shown automatically in the sidebar after scoring.
    Falls back to a heuristic sentence when AI is unavailable.
    """
    from ..ai.client import available, generate_text
    from ..models import Resume as _Resume

    profile = _load_profile(db, user, materialize=False)
    match = score_job({"title": job.title, "company": job.company,
                        "description_snippet": job.description_snippet,
                        "location": job.location}, profile)
    elig = eligibility({"title": job.title, "company": job.company,
                         "description_snippet": job.description_snippet,
                         "location": job.location, "employment_type": job.employment_type},
                        profile)

    resume_skills = profile.get("skills", [])
    job_text = f"{job.title} {job.description_snippet}".lower()
    matching = [s for s in resume_skills if s.lower() in job_text]
    missing  = [s for s in resume_skills if s.lower() not in job_text]

    if available():
        res_row = db.query(_Resume).filter_by(user_id=user.id).first()
        resume_text = ""
        if res_row and res_row.raw_text:
            from ..security import decrypt_value
            try:
                resume_text = decrypt_value(res_row.raw_text) if res_row.raw_text else ""
            except Exception:
                resume_text = res_row.raw_text or ""

        task = (
            f"Job: {job.title} at {job.company} ({job.location or 'Unknown location'})\n"
            f"Match score: {match['score']}/100. Tier: {elig['eligibility_tier']}.\n"
            f"Matching skills: {', '.join(matching[:6]) or 'none identified'}.\n"
            f"Missing skills: {', '.join(missing[:5]) or 'none identified'}.\n\n"
            "Write exactly 2 sentences summarising this job match for the candidate. "
            "Be specific about skills — mention which ones match and which are gaps. "
            "Do not start with 'This'. Be direct and honest."
        )
        summary = generate_text(task, resume_text=resume_text, max_tokens=160)
        if summary:
            return {"summary": summary, "ai": True}

    # Heuristic fallback.
    tier = elig.get("eligibility_tier", "Possible Match")
    score = match["score"]
    if matching:
        base = f"Your top matching skills are {', '.join(matching[:3])} ({score}% overall match)."
    else:
        base = f"Resume match is {score}% — no clear skill overlap found for this role."
    gap = f" Key gaps: {', '.join(missing[:3])}." if missing else ""
    return {"summary": base + gap, "ai": False}
