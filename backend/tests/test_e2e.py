"""End-to-end journeys via TestClient: signup → resume → search → track →
verify, plus Lever/Ashby Assisted Apply. Job search is stubbed to canned real-
shaped jobs so the tests are deterministic (no live provider network)."""
import io

import pytest

from app.cache import cache
from app.jobs import aggregator
from app.jobs.base import RawJob


def _pdf() -> bytes:
    txt = "E2E Candidate e2e@example.com Python Machine Learning React"
    stream = "BT /F1 11 Tf 50 760 Td (%s) Tj ET" % txt
    objs = ["<< /Type /Catalog /Pages 2 0 R >>",
            "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
            "/Resources << /Font << /F1 5 0 R >> >> >>",
            "<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    pdf = "%PDF-1.4\n"; offs = []
    for i, o in enumerate(objs, 1):
        offs.append(len(pdf)); pdf += "%d 0 obj\n%s\nendobj\n" % (i, o)
    x = len(pdf); pdf += "xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for o in offs:
        pdf += "%010d 00000 n \n" % o
    pdf += "trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objs) + 1, x)
    return pdf.encode("latin-1")


def H(t):
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    # Clear rate-limit counters so login isn't starved by test_b2's limit test.
    cache.clear_prefix("rl:")
    yield


@pytest.fixture()
def stub_search(monkeypatch):
    """Stub the aggregator so /jobs returns deterministic, real-shaped jobs."""
    jobs = [
        RawJob(source="Greenhouse", title="Software Engineer Intern", company="Stripe",
               apply_url="https://boards.greenhouse.io/stripe?gh_jid=1",
               location="Remote", remote=True, employment_type="internship",
               external_id="gh-1", company_domain="greenhouse.io").to_dict(),
        RawJob(source="Lever", title="New Grad Software Engineer", company="Ro",
               apply_url="https://jobs.lever.co/ro/abc/apply",
               location="Remote", remote=True, external_id="lv-1",
               company_domain="lever.co").to_dict(),
    ]

    async def fake_search(*a, **k):
        return jobs
    monkeypatch.setattr(aggregator, "search", fake_search)
    return jobs


@pytest.fixture(scope="session")
def journey_user(client):
    """Signup + login via the REAL endpoints (E2E). Approval is applied directly
    in the DB (admin-approval is covered elsewhere); rate-limit pre-cleared."""
    from app.database import SessionLocal
    from app.models import User

    cache.clear_prefix("rl:")
    email = "e2e@example.com"
    reg = client.post("/api/auth/register", json={
        "full_name": "E2E Candidate", "email": email, "password": "E2eTest123",
        "years_experience": 0})
    assert reg.status_code == 200, reg.text
    assert reg.json()["status"] == "pending"   # signup starts pending approval

    db = SessionLocal()
    try:
        u = db.query(User).filter_by(email=email).first()
        u.status = "approved"
        u.seeker_type = "student"   # drives the internship-first filter
        db.commit()
    finally:
        db.close()

    cache.clear_prefix("rl:")
    login = client.post("/api/auth/login", json={"email": email, "password": "E2eTest123"})
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


# ---------------------------------------------------------------- journeys
def test_e2e_signup_resume_search_track_verify(client, journey_user, stub_search):
    tok = journey_user

    # Resume upload
    up = client.post("/api/resume/upload", headers=H(tok),
                     files={"file": ("r.pdf", io.BytesIO(_pdf()), "application/pdf")})
    assert up.status_code == 200, up.text
    assert client.get("/api/resume/parsed", headers=H(tok)).json()["parsed_email"] == "e2e@example.com"

    # Job search (stubbed) — eligibility + internship filter applied. min_match=0
    # disables the resume match-score threshold (this journey test isn't testing
    # that filter; the stub jobs intentionally have empty descriptions).
    jr = client.get("/api/jobs?q=software&min_match=0", headers=H(tok))
    assert jr.status_code == 200, jr.text
    items = jr.json()["items"]
    titles = [i["title"] for i in items]
    assert "Software Engineer Intern" in titles  # intern signal passes the filter
    gh = next(i for i in items if i["platform"] == "Greenhouse")
    assert gh["eligibility_tier"] in ("Excellent Match", "Good Match")
    assert gh["early_signal"] == "Internship"

    # Greenhouse Track & Apply → Tracked (never "Applied")
    tr = client.post("/api/jobs/apply", headers=H(tok), json={
        "fingerprint": gh["fingerprint"], "source": "Greenhouse", "title": gh["title"],
        "company": gh["company"], "apply_url": gh["apply_url"], "platform": "Greenhouse",
        "manual_required": False, "status": "Tracked"})
    assert tr.status_code == 200 and tr.json()["display_status"] == "Tracked"

    # Activity / Verification data — present, no "Applied" leak
    apps = client.get("/api/applications", headers=H(tok)).json()["items"]
    assert any(a["company"] == "Stripe" and a["display_status"] == "Tracked" for a in apps)
    assert not any(a["display_status"] == "Applied" for a in apps)


def test_e2e_lever_assisted_apply_verified(client, journey_user):
    tok = journey_user
    client.post("/api/resume/upload", headers=H(tok),
                files={"file": ("r.pdf", io.BytesIO(_pdf()), "application/pdf")})
    prep = client.post("/api/jobs/assisted/prepare", headers=H(tok), json={"job": {
        "title": "New Grad SWE", "company": "Ro", "apply_url": "https://jobs.lever.co/ro/x/apply",
        "source": "Lever", "fingerprint": "e2e-lever-1"}})
    assert prep.status_code == 200 and prep.json()["platform"] == "Lever"
    app_id = prep.json()["application_id"]

    rec = client.post("/api/jobs/assisted/record", headers=H(tok),
                      data={"application_id": str(app_id),
                            "confirmation_url": "https://jobs.lever.co/ro/x/thanks",
                            "reference_id": "LVR-E2E1"},
                      files={"screenshot": ("c.png", io.BytesIO(b"\x89PNGfake"), "image/png")})
    assert rec.status_code == 200 and rec.json()["display_status"] == "Verified Submitted"

    ev = client.get(f"/api/applications/{app_id}/evidence", headers=H(tok)).json()
    assert ev["display_status"] == "Verified Submitted" and ev["reference_id"] == "LVR-E2E1"


def test_e2e_ashby_assisted_partial_is_submitted(client, journey_user):
    tok = journey_user
    client.post("/api/resume/upload", headers=H(tok),
                files={"file": ("r.pdf", io.BytesIO(_pdf()), "application/pdf")})
    prep = client.post("/api/jobs/assisted/prepare", headers=H(tok), json={"job": {
        "title": "ML Intern", "company": "Ramp", "apply_url": "https://jobs.ashbyhq.com/Ramp/x/application",
        "source": "Ashby", "fingerprint": "e2e-ashby-1"}})
    assert prep.status_code == 200 and prep.json()["platform"] == "Ashby"
    app_id = prep.json()["application_id"]

    # No screenshot → must be "Submitted", never "Verified Submitted"
    rec = client.post("/api/jobs/assisted/record", headers=H(tok),
                      data={"application_id": str(app_id),
                            "confirmation_url": "https://jobs.ashbyhq.com/Ramp/x/application",
                            "reference_id": "ASH-E2E1"})
    assert rec.status_code == 200
    assert rec.json()["display_status"] == "Submitted"
    assert rec.json()["verified"] is False
