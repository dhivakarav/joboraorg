"""Searching an explicit role must return roles matching THAT query — not the
user's stored profile role. Regression for: searching "data engineer" returned
"Software Engineer" results (reason 'Title matches "software engineer"') because
the query was never passed to the matcher and the title filter only required one
shared term ("engineer").
"""
import time

from app.automation.matcher import score_job
from app.database import SessionLocal
from app.models import JobFilter, User
from app.security import hash_password, issue_tokens


# ---- matcher: the explicit query is the primary role signal --------------------
def test_query_drives_match_reason():
    profile = {"skills": [], "roles": ["software engineer"], "keywords": [], "experience": 0}
    job = {"title": "Data Engineer", "description_snippet": "build ETL pipelines"}
    res = score_job(job, profile, query="data engineer")
    assert any("data engineer" in r.lower() for r in res["reasons"])
    # The stored profile role must NOT be the claimed reason for a Data Engineer job.
    assert not any("software engineer" in r.lower() for r in res["reasons"])


def test_no_query_keeps_profile_behaviour():
    profile = {"skills": [], "roles": ["software engineer"], "keywords": [], "experience": 0}
    job = {"title": "Software Engineer", "description_snippet": ""}
    res = score_job(job, profile)   # no query → unchanged
    assert any("software engineer" in r.lower() for r in res["reasons"])


# ---- leadership / executive titles must not match a technical-role search -------
def test_leadership_title_excluded_from_technical_search():
    # Strong skill overlap must NOT rescue an off-target leadership title.
    profile = {"skills": ["python", "sql"], "roles": ["software engineer"],
               "keywords": [], "experience": 0}
    job = {"title": "Vice President of Software Engineering",
           "description_snippet": "python sql leadership"}
    res = score_job(job, profile, query="data engineer")
    assert res["score"] <= 15                       # capped — excluded by any sane floor
    assert not any("title matches" in r.lower() for r in res["reasons"])


def test_seniority_modifier_still_matches():
    # "Senior Data Engineer" IS a data engineer — must keep matching.
    profile = {"skills": ["python"], "roles": ["software engineer"], "keywords": [], "experience": 0}
    res = score_job({"title": "Senior Data Engineer", "description_snippet": "python etl"},
                    profile, query="data engineer")
    assert res["score"] >= 50


def test_leadership_search_matches_leadership_titles():
    # If the user actually searches a leadership role, leadership titles match.
    profile = {"skills": ["python"], "roles": [], "keywords": [], "experience": 8}
    res = score_job({"title": "VP of Engineering", "description_snippet": "python"},
                    profile, query="vp engineering")
    assert res["score"] >= 50


# ---- endpoint: strict title relevance excludes off-target roles ----------------
def _user():
    db = SessionLocal()
    try:
        u = User(full_name="Q", email=f"q{int(time.time()*1e6)}@example.com",
                 hashed_password=hash_password("x"), status="approved", seeker_type="fresher")
        db.add(u); db.commit(); db.refresh(u)
        db.add(JobFilter(user_id=u.id, min_match_score=0)); db.commit()
        return issue_tokens(u)["access_token"]
    finally:
        db.close()


def test_explicit_query_excludes_offtarget(client, monkeypatch):
    tok = _user()
    H = {"Authorization": f"Bearer {tok}"}

    def job(title, code):
        return {
            "fingerprint": f"fp-{code}", "external_id": code, "source": "Greenhouse",
            "source_domain": "boards.greenhouse.io", "title": title, "company": "Acme",
            "location": "Bengaluru, India", "salary": "", "salary_inr": "", "deadline": "",
            "posted_at": "2026-06-20", "remote": False, "job_type": "Full Time",
            "employment_type": "job", "duration": "", "verified": True,
            "apply_url": f"https://boards.greenhouse.io/acme/jobs/{code}",
            "description_snippet": "engineering role",
        }

    pool = [job("Data Engineer", "1"), job("Senior Data Engineer", "2"),
            job("Software Engineer", "3"), job("iOS Engineer", "4")]

    async def fake_search(*a, **k):
        return pool
    monkeypatch.setattr("app.routers.jobs.aggregator.search", fake_search)

    resp = client.get("/api/jobs?q=data+engineer&include_ineligible=true&internships_only=false",
                      headers=H).json()
    titles = [i["title"] for i in resp["items"]]
    assert "Data Engineer" in titles
    assert "Senior Data Engineer" in titles
    assert "Software Engineer" not in titles      # shares "engineer" but lacks "data"
    assert "iOS Engineer" not in titles
