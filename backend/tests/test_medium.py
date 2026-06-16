"""Medium-tier coverage: assisted apply, verification, status transitions,
search caching, and the Greenhouse Track & Apply flow."""
import io
import types

import pytest


# ----------------------------------------------------------------------------
# Helpers / fixtures
# ----------------------------------------------------------------------------
def _minimal_pdf() -> bytes:
    txt = "Test Candidate test@example.com Python Machine Learning"
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


@pytest.fixture(scope="session")
def user_token(client):
    """An approved user's token, created directly in the DB + issued via security.

    Avoids the /auth/login endpoint entirely so this fixture never collides with
    the per-IP login rate limit that test_b2 deliberately exhausts.
    """
    from app.database import SessionLocal
    from app.models import User
    from app.security import hash_password, issue_tokens
    db = SessionLocal()
    try:
        email = "medium_user@example.com"
        u = db.query(User).filter_by(email=email).first()
        if not u:
            u = User(full_name="Medium User", email=email,
                     hashed_password=hash_password("UserTest123"), status="approved",
                     is_admin=False, seeker_type="student", years_experience=0,
                     email_verified=True)
            db.add(u); db.commit(); db.refresh(u)
        return issue_tokens(u)["access_token"]
    finally:
        db.close()


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


# ----------------------------------------------------------------------------
# 1. Status transitions (pure, evidence-gated)
# ----------------------------------------------------------------------------
from app.status import display_status, evidence_complete


def _app(**kw):
    base = dict(submission_status="", status="", manual_required=False,
                application_id="", external_application_id="", confirmation_url="",
                evidence_available=False)
    base.update(kw)
    return types.SimpleNamespace(**base)


def test_status_verified_requires_all_evidence():
    full = _app(submission_status="Verified Submitted", application_id="GH-1",
                confirmation_url="https://x/thanks", evidence_available=True)
    assert evidence_complete(full) and display_status(full) == "Verified Submitted"


def test_status_verified_without_evidence_downgrades_to_submitted():
    partial = _app(submission_status="Verified Submitted", application_id="GH-1",
                   confirmation_url="", evidence_available=False)
    assert not evidence_complete(partial)
    assert display_status(partial) == "Submitted"


def test_status_legacy_applied_never_surfaces():
    legacy = _app(status="Applied", submission_status="Draft")
    assert display_status(legacy) == "Tracked"  # never "Applied"


def test_status_manual_and_tracked():
    assert display_status(_app(submission_status="Manual Apply")) == "Manual Apply"
    assert display_status(_app(submission_status="Draft", status="Tracked")) == "Tracked"
    assert display_status(_app(submission_status="Draft", status="Saved")) == "Draft"


# ----------------------------------------------------------------------------
# 2. Search caching + query-agnostic providers
# ----------------------------------------------------------------------------
from app.jobs import aggregator as agg
from app.jobs.providers.greenhouse import GreenhouseProvider
from app.jobs.providers.remotive import RemotiveProvider


def test_query_agnostic_key_ignores_query():
    gh = GreenhouseProvider()
    assert gh.query_agnostic is True
    # agnostic provider → same key regardless of query
    assert agg._provider_key(gh, "software", "") == agg._provider_key(gh, "data analyst", "")


def test_query_specific_key_varies_by_query():
    rem = RemotiveProvider()
    assert getattr(rem, "query_agnostic", False) is False
    assert agg._provider_key(rem, "software", "") != agg._provider_key(rem, "data analyst", "")


def test_provider_cache_clear():
    agg._provider_cache["x|y|z"] = (9e18, [])
    agg.clear_provider_cache()
    assert agg._provider_cache == {}


# ----------------------------------------------------------------------------
# 3. Greenhouse Track & Apply flow
# ----------------------------------------------------------------------------
def test_greenhouse_track_and_apply_records_tracked(client, user_token):
    r = client.post("/api/jobs/apply", headers=H(user_token), json={
        "fingerprint": "gh-track-1", "source": "Greenhouse", "title": "SWE Intern",
        "company": "Stripe", "apply_url": "https://stripe.com/jobs?gh_jid=1",
        "platform": "Greenhouse", "manual_required": False, "status": "Tracked"})
    assert r.status_code == 200, r.text
    assert r.json()["display_status"] == "Tracked"


def test_apply_coerces_legacy_applied_to_tracked(client, user_token):
    r = client.post("/api/jobs/apply", headers=H(user_token), json={
        "fingerprint": "gh-track-2", "source": "Greenhouse", "title": "SWE Intern 2",
        "company": "Airbnb", "apply_url": "https://x?gh_jid=2",
        "platform": "Greenhouse", "manual_required": False, "status": "Applied"})
    assert r.status_code == 200
    assert r.json()["display_status"] == "Tracked"   # never "Applied"


# ----------------------------------------------------------------------------
# 4. Assisted Apply (Lever) + 5. Verification (evidence) end-to-end
# ----------------------------------------------------------------------------
def test_assisted_apply_prepare_and_evidence_gate(client, user_token):
    # need a resume first
    up = client.post("/api/resume/upload", headers=H(user_token),
                     files={"file": ("resume.pdf", io.BytesIO(_minimal_pdf()), "application/pdf")})
    assert up.status_code == 200, up.text

    prep = client.post("/api/jobs/assisted/prepare", headers=H(user_token), json={"job": {
        "title": "Software Engineer Intern", "company": "Ro",
        "apply_url": "https://jobs.lever.co/ro/abc/apply", "source": "Lever",
        "fingerprint": "lever-assist-1"}})
    assert prep.status_code == 200, prep.text
    body = prep.json()
    assert body["platform"] == "Lever"
    assert any(f["label"] == "Full name" for f in body["required_fields"])
    app_id = body["application_id"]

    # record WITHOUT screenshot → "Submitted" (partial proof), NOT verified
    r1 = client.post("/api/jobs/assisted/record", headers=H(user_token),
                     data={"application_id": str(app_id),
                           "confirmation_url": "https://jobs.lever.co/ro/abc/thanks",
                           "reference_id": "LVR-TEST123"})
    assert r1.status_code == 200, r1.text
    assert r1.json()["display_status"] == "Submitted"
    assert r1.json()["verified"] is False
    assert "screenshot" in r1.json()["missing"]

    # record WITH all three proofs → "Verified Submitted"
    r2 = client.post("/api/jobs/assisted/record", headers=H(user_token),
                     data={"application_id": str(app_id),
                           "confirmation_url": "https://jobs.lever.co/ro/abc/thanks",
                           "reference_id": "LVR-TEST123"},
                     files={"screenshot": ("conf.png", io.BytesIO(b"\x89PNG\r\n\x1a\nfake"), "image/png")})
    assert r2.status_code == 200, r2.text
    assert r2.json()["display_status"] == "Verified Submitted"
    assert r2.json()["verified"] is True

    # Verification Center data: the row shows up with evidence + canonical status
    ev = client.get(f"/api/applications/{app_id}/evidence", headers=H(user_token))
    assert ev.status_code == 200, ev.text
    e = ev.json()
    assert e["display_status"] == "Verified Submitted"
    assert e["reference_id"] == "LVR-TEST123"
    assert e["confirmation_url"].endswith("/thanks")


def test_assisted_apply_rejects_non_assisted_platform(client, user_token):
    client.post("/api/resume/upload", headers=H(user_token),
                files={"file": ("r.pdf", io.BytesIO(_minimal_pdf()), "application/pdf")})
    r = client.post("/api/jobs/assisted/prepare", headers=H(user_token), json={"job": {
        "title": "X", "company": "Y", "apply_url": "https://boards.greenhouse.io/x?gh_jid=9",
        "source": "Greenhouse", "fingerprint": "gh-not-assisted"}})
    assert r.status_code == 400  # Greenhouse is Track & Apply, not assisted


# ----------------------------------------------------------------------------
# 6. Dead code removed: portals/billing endpoints are gone
# ----------------------------------------------------------------------------
def test_removed_endpoints_return_404(client, user_token):
    assert client.get("/api/portals", headers=H(user_token)).status_code == 404
    assert client.get("/api/billing/plans", headers=H(user_token)).status_code == 404
