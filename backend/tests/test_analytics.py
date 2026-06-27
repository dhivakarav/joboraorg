"""Tests for GET /api/jobs/analytics — aggregator-driven discovery analytics.

Verifies that the endpoint reflects what the aggregator.search() returned
(the same source the scanner engine uses), NOT the Application table.

The previous broken implementation (a5dc986) read the Application table.
That caused "Jobs Discovered" to stay frozen when a scan found jobs that were
all already tracked — 0 new Application rows → count unchanged even though
the providers returned 169 fresh openings.
"""
import pytest

from app.database import SessionLocal
from app.jobs import aggregator
from app.jobs.base import RawJob
from app.models import User
from app.security import hash_password, issue_tokens


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


def _make_jobs(*specs) -> list:
    """Build a list of RawJob.to_dict() from (source, title, location) tuples."""
    out = []
    for i, (source, title, location) in enumerate(specs):
        out.append(RawJob(
            source=source, title=title, company=f"Co{i}",
            apply_url=f"https://boards.greenhouse.io/co{i}/jobs/{i}",
            location=location, remote="remote" in location.lower(),
            external_id=f"ext-{i}",
        ).to_dict())
    return out


@pytest.fixture(scope="module")
def analytics_token(client):
    """Approved user with no pre-existing applications so counts are clean."""
    db = SessionLocal()
    try:
        email = "analytics2_user@example.com"
        u = db.query(User).filter_by(email=email).first()
        if not u:
            u = User(
                full_name="Analytics2 User",
                email=email,
                hashed_password=hash_password("Analytics2Test123"),
                status="approved",
                is_admin=False,
                seeker_type="student",
                years_experience=0,
                email_verified=True,
            )
            db.add(u)
            db.commit()
            db.refresh(u)
        return issue_tokens(u)["access_token"]
    finally:
        db.close()


@pytest.fixture()
def stub_aggregator(monkeypatch):
    """Stub aggregator.search() with a deterministic set of jobs.

    4 jobs total:
      - 2 Greenhouse (1 intern, 1 ML Engineer → ai_ml)
      - 1 Lever     (New Grad → fresher)
      - 1 Remotive  (plain Backend Developer)
    """
    jobs = _make_jobs(
        ("Greenhouse", "Software Engineer Intern", "Bangalore, India"),
        ("Greenhouse", "Machine Learning Engineer", "Remote"),
        ("Lever",      "New Grad Software Engineer", "Hyderabad, India"),
        ("Remotive",   "Backend Developer", "Remote"),
    )

    async def fake_search(*a, **k):
        return jobs

    monkeypatch.setattr(aggregator, "search", fake_search)
    return jobs


def test_analytics_counts_from_aggregator_not_application_table(
    client, analytics_token, stub_aggregator
):
    """jobs_discovered must equal the number of jobs returned by aggregator.search(),
    regardless of how many Application rows exist for this user."""
    r = client.get("/api/jobs/analytics", headers=H(analytics_token))
    assert r.status_code == 200, r.text
    data = r.json()

    # aggregator returned 4 jobs → analytics must show 4
    assert data["jobs_discovered"] == 4, (
        f"Expected 4 (aggregator count), got {data['jobs_discovered']}. "
        "If this shows the Application table count the fix is incomplete."
    )


def test_analytics_employment_type_breakdown(client, analytics_token, stub_aggregator):
    """Internship and fresher counts are derived from aggregator job titles."""
    r = client.get("/api/jobs/analytics", headers=H(analytics_token))
    data = r.json()

    assert data["internships"] == 1   # "Software Engineer Intern"
    assert data["freshers"] == 1      # "New Grad Software Engineer"


def test_analytics_ai_ml_count(client, analytics_token, stub_aggregator):
    """AI/ML count uses is_ai_ml(title, snippet) on aggregator results."""
    r = client.get("/api/jobs/analytics", headers=H(analytics_token))
    data = r.json()

    assert data["ai_ml"] == 1         # "Machine Learning Engineer"


def test_analytics_by_source_from_aggregator(client, analytics_token, stub_aggregator):
    """by_source reflects provider breakdown in aggregator results."""
    r = client.get("/api/jobs/analytics", headers=H(analytics_token))
    data = r.json()
    by_source = data["by_source"]

    assert by_source.get("Greenhouse") == 2
    assert by_source.get("Lever") == 1
    assert by_source.get("Remotive") == 1


def test_analytics_provider_status_always_present(client, analytics_token, stub_aggregator):
    """live_providers, total_providers, last_sync are always in the response."""
    r = client.get("/api/jobs/analytics", headers=H(analytics_token))
    data = r.json()

    assert "live_providers" in data
    assert "total_providers" in data
    assert data["total_providers"] >= 1
    assert "last_sync" in data


def test_analytics_reflects_new_aggregator_results_immediately(
    client, analytics_token, monkeypatch
):
    """Changing what aggregator.search() returns immediately changes the analytics
    response — there is no Application-table or response cache hiding stale values."""
    # First call: 2 jobs
    jobs_small = _make_jobs(
        ("Greenhouse", "Data Scientist", "Remote"),
        ("Lever",      "ML Intern", "Bangalore, India"),
    )

    async def fake_small(*a, **k):
        return jobs_small

    monkeypatch.setattr(aggregator, "search", fake_small)
    r1 = client.get("/api/jobs/analytics", headers=H(analytics_token))
    assert r1.json()["jobs_discovered"] == 2

    # Second call: 5 jobs (simulates a new scan with more results)
    jobs_large = _make_jobs(
        ("Greenhouse", "Data Scientist", "Remote"),
        ("Greenhouse", "ML Engineer", "Bangalore, India"),
        ("Lever",      "ML Intern", "Hyderabad, India"),
        ("Remotive",   "AI Researcher", "Remote"),
        ("Jooble",     "Backend Developer", "Chennai, India"),
    )

    async def fake_large(*a, **k):
        return jobs_large

    monkeypatch.setattr(aggregator, "search", fake_large)
    r2 = client.get("/api/jobs/analytics", headers=H(analytics_token))
    assert r2.json()["jobs_discovered"] == 5, (
        "Analytics must reflect the current aggregator result, not a cached/DB value"
    )
