"""The 'Minimum resume match score' filter is a HARD FLOOR everywhere jobs are
shown — Find Jobs, Matched Jobs, and the Pending Approval queue. A job scored
below the user's threshold must never appear on any of these surfaces, with no
silent fallback to a lower number.
"""
import time

from app.database import SessionLocal
from app.models import Application, JobFilter, User
from app.security import hash_password, issue_tokens


def _user_with_threshold(min_match: int):
    """Create an approved user whose Filters min_match_score = `min_match`."""
    db = SessionLocal()
    try:
        u = User(full_name="Floor Tester", email=f"floor{int(time.time()*1e6)}@example.com",
                 hashed_password=hash_password("x"), status="approved", seeker_type="fresher")
        db.add(u); db.commit(); db.refresh(u)
        db.add(JobFilter(user_id=u.id, min_match_score=min_match))
        db.commit()
        return u.id, issue_tokens(u)["access_token"]
    finally:
        db.close()


def _record(uid, *, match, source, sub_status, title):
    # application_mode is DERIVED from `source` by a model event listener, so we set
    # the source: an auto ATS (Greenhouse) → auto_applied; a manual portal (Naukri)
    # → manual_link_provided.
    db = SessionLocal()
    try:
        a = Application(
            user_id=uid, portal=source, source=source, platform=source,
            job_title=title, company="Acme",
            apply_url="https://example.com/jobs/1",
            match_score=match,
            job_url_hash=f"floor-{title}-{int(time.time()*1e6)}",
            status="Pending", submission_status=sub_status)
        db.add(a); db.commit(); db.refresh(a)
        return a.id
    finally:
        db.close()


def test_min_match_floor_on_matched_jobs(client):
    """Matched Jobs (mode=manual_link_provided) hides rows below the threshold."""
    uid, tok = _user_with_threshold(35)
    H = {"Authorization": f"Bearer {tok}"}
    above = _record(uid, match=60, source="Naukri", sub_status="Manual Apply", title="above-mj")
    below = _record(uid, match=18, source="Naukri", sub_status="Manual Apply", title="below-mj")

    items = client.get("/api/applications?mode=manual_link_provided&page_size=100",
                       headers=H).json()["items"]
    ids = {i["id"] for i in items}
    assert above in ids                  # 60% ≥ 35% → shown
    assert below not in ids              # 18% < 35% → hidden, no exceptions


def test_min_match_floor_on_pending_queue(client):
    """The Pending Approval queue hides rows below the threshold even if they were
    queued earlier under a lower one."""
    uid, tok = _user_with_threshold(35)
    H = {"Authorization": f"Bearer {tok}"}
    above = _record(uid, match=72, source="Greenhouse", sub_status="Pending Approval", title="above-pa")
    below = _record(uid, match=20, source="Greenhouse", sub_status="Pending Approval", title="below-pa")

    items = client.get("/api/apply/pending", headers=H).json()["items"]
    ids = {i["id"] for i in items}
    assert above in ids
    assert below not in ids


def _job(title, url):
    return {
        "fingerprint": f"fp-{title}", "external_id": title, "source": "Greenhouse",
        "source_domain": "boards.greenhouse.io", "title": title, "company": "Acme",
        "location": "Bengaluru, India", "salary": "", "salary_inr": "", "deadline": "",
        "posted_at": "2026-06-20", "remote": False, "job_type": "Full Time",
        "employment_type": "job", "duration": "", "apply_url": url,
        "description_snippet": "Build software with Python and React.", "verified": True,
    }


def test_min_match_floor_on_find_jobs(client, monkeypatch):
    """Find Jobs hides any job scored below the user's threshold."""
    uid, tok = _user_with_threshold(35)
    H = {"Authorization": f"Bearer {tok}"}

    jobs = [_job("High Match Engineer", "https://boards.greenhouse.io/acme/jobs/111"),
            _job("Low Match Engineer", "https://boards.greenhouse.io/acme/jobs/222")]

    async def fake_search(*a, **k):
        return jobs
    # Deterministic scores: title decides — one above 35, one below.
    def fake_score(job, profile, query=""):
        hi = "High" in job.get("title", "")
        return {"score": 80 if hi else 12, "reasons": []}

    monkeypatch.setattr("app.routers.jobs.aggregator.search", fake_search)
    monkeypatch.setattr("app.routers.jobs.score_job", fake_score)

    resp = client.get("/api/jobs?q=engineer&include_ineligible=true&internships_only=false",
                      headers=H).json()
    titles = {i["title"] for i in resp["items"]}
    assert "High Match Engineer" in titles      # 80% ≥ 35%
    assert "Low Match Engineer" not in titles   # 12% < 35% → hidden everywhere
    assert resp["min_match"] == 35


def test_funnel_rows_exempt_from_floor(client):
    """A job the user actively advanced (Interview/Offer) is NOT hidden by raising
    the slider — that would lose sight of a real, in-progress application."""
    uid, tok = _user_with_threshold(90)   # very high floor
    H = {"Authorization": f"Bearer {tok}"}
    db = SessionLocal()
    try:
        a = Application(user_id=uid, portal="Greenhouse", source="Greenhouse",
                        platform="Greenhouse", job_title="interviewing", company="Acme",
                        apply_url="https://boards.greenhouse.io/acme/jobs/2", match_score=40,
                        job_url_hash=f"funnel-{int(time.time()*1e6)}",
                        status="Interview", submission_status="Manual Apply")
        db.add(a); db.commit(); aid = a.id
    finally:
        db.close()
    items = client.get("/api/applications?page_size=100", headers=H).json()["items"]
    assert aid in {i["id"] for i in items}   # 40% < 90% but it's in the human funnel → kept
