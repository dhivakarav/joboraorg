"""Tests for GET /api/jobs/analytics — DB-driven discovery analytics.

Verifies that the endpoint reads live Application rows from PostgreSQL
(not from a cached aggregator.search() call), so the cards always reflect
what the user has actually tracked.
"""
import pytest

from app.database import SessionLocal
from app.models import Application, User
from app.security import hash_password, issue_tokens


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def analytics_token(client):
    """Approved user with a clean application set for analytics assertions."""
    db = SessionLocal()
    try:
        email = "analytics_user@example.com"
        u = db.query(User).filter_by(email=email).first()
        if not u:
            u = User(
                full_name="Analytics User",
                email=email,
                hashed_password=hash_password("AnalyticsTest123"),
                status="approved",
                is_admin=False,
                seeker_type="student",
                years_experience=0,
                email_verified=True,
            )
            db.add(u)
            db.commit()
            db.refresh(u)

        # Wipe any applications left from previous runs so counts are deterministic.
        db.query(Application).filter_by(user_id=u.id).delete()
        db.commit()

        # Seed known applications directly in the DB (bypass the API so we control
        # every field, including match_score and job_title).
        apps = [
            Application(user_id=u.id, portal="Greenhouse", source="Greenhouse",
                        job_title="Software Engineer Intern", company="Stripe",
                        apply_url="https://boards.greenhouse.io/stripe/jobs/1",
                        job_url_hash="hash-intern-1", match_score=80,
                        status="Tracked", submission_status="Draft"),
            Application(user_id=u.id, portal="Lever", source="Lever",
                        job_title="New Grad Software Engineer", company="Ro",
                        apply_url="https://jobs.lever.co/ro/abc",
                        job_url_hash="hash-fresher-1", match_score=70,
                        status="Tracked", submission_status="Draft"),
            Application(user_id=u.id, portal="Jooble", source="Jooble",
                        job_title="Machine Learning Engineer", company="DeepMind",
                        apply_url="https://jooble.org/desc/ml-1",
                        job_url_hash="hash-aiml-1", match_score=90,
                        status="Tracked", submission_status="Draft"),
            Application(user_id=u.id, portal="Remotive", source="Remotive",
                        job_title="Backend Developer", company="Acme",
                        apply_url="https://remotive.com/remote-jobs/backend/1",
                        job_url_hash="hash-job-1", match_score=30,
                        status="Tracked", submission_status="Draft"),
        ]
        for a in apps:
            db.add(a)
        db.commit()

        return issue_tokens(u)["access_token"]
    finally:
        db.close()


def test_analytics_reads_from_db(client, analytics_token):
    """The endpoint returns counts that exactly match what is in the Application table."""
    r = client.get("/api/jobs/analytics", headers=H(analytics_token))
    assert r.status_code == 200, r.text
    data = r.json()

    # 4 seeded applications total.
    assert data["jobs_discovered"] == 4

    # Employment-type breakdown from job titles.
    assert data["internships"] == 1   # "Software Engineer Intern"
    assert data["freshers"] == 1      # "New Grad Software Engineer"

    # AI/ML count from job title signal.
    assert data["ai_ml"] == 1         # "Machine Learning Engineer"


def test_analytics_coverage_uses_match_score(client, analytics_token):
    """Coverage = fraction of tracked jobs meeting min_match threshold (default 50)."""
    r = client.get("/api/jobs/analytics", headers=H(analytics_token))
    assert r.status_code == 200, r.text
    data = r.json()

    # 3 of 4 apps have match_score >= 50 (80, 70, 90 qualify; 30 does not).
    assert data["coverage_percentage"] == 75


def test_analytics_by_source_breakdown(client, analytics_token):
    """by_source groups application counts by the source column."""
    r = client.get("/api/jobs/analytics", headers=H(analytics_token))
    assert r.status_code == 200, r.text
    by_source = r.json()["by_source"]

    assert by_source.get("Greenhouse") == 1
    assert by_source.get("Lever") == 1
    assert by_source.get("Jooble") == 1
    assert by_source.get("Remotive") == 1


def test_analytics_provider_status_included(client, analytics_token):
    """Provider connectivity fields are always present."""
    r = client.get("/api/jobs/analytics", headers=H(analytics_token))
    assert r.status_code == 200, r.text
    data = r.json()

    assert "live_providers" in data
    assert "total_providers" in data
    assert data["total_providers"] >= 1
    assert "last_sync" in data


def test_analytics_reflects_new_application_immediately(client, analytics_token):
    """Adding an application to the DB is reflected on the next analytics call
    — there is no cache layer between the endpoint and the database."""
    r_before = client.get("/api/jobs/analytics", headers=H(analytics_token))
    count_before = r_before.json()["jobs_discovered"]

    # Insert one more application directly.
    db = SessionLocal()
    try:
        from app.models import User as _User
        u = db.query(_User).filter_by(email="analytics_user@example.com").first()
        extra = Application(
            user_id=u.id, portal="Arbeitnow", source="Arbeitnow",
            job_title="Data Analyst", company="NewCo",
            apply_url="https://arbeitnow.com/view/data-analyst-newco-1",
            job_url_hash="hash-extra-1", match_score=60,
            status="Tracked", submission_status="Draft",
        )
        db.add(extra)
        db.commit()
    finally:
        db.close()

    r_after = client.get("/api/jobs/analytics", headers=H(analytics_token))
    assert r_after.json()["jobs_discovered"] == count_before + 1
