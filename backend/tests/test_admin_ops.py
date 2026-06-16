"""Admin Operations endpoints: metrics, invite codes, feedback triage."""
import pytest


@pytest.fixture(scope="session")
def admin_tok(client):
    """An admin token created directly in the DB (no login endpoint → no rate-limit)."""
    from app.database import SessionLocal
    from app.models import User
    from app.security import hash_password, issue_tokens
    db = SessionLocal()
    try:
        email = "ops_admin@example.com"
        u = db.query(User).filter_by(email=email).first()
        if not u:
            u = User(full_name="Ops Admin", email=email,
                     hashed_password=hash_password("OpsAdmin123"), status="approved",
                     is_admin=True, email_verified=True)
            db.add(u); db.commit(); db.refresh(u)
        return issue_tokens(u)["access_token"]
    finally:
        db.close()


def H(t):
    return {"Authorization": f"Bearer {t}"}


def test_admin_metrics_shape(client, admin_tok):
    r = client.get("/api/admin/metrics", headers=H(admin_tok))
    assert r.status_code == 200, r.text
    m = r.json()
    for key in ("users", "funnel", "applications", "feedback", "invites"):
        assert key in m
    assert "verified_submitted" in m["applications"]
    assert "signed_up" in m["funnel"]


def test_admin_invites_create_and_list(client, admin_tok):
    before = len(client.get("/api/admin/invites", headers=H(admin_tok)).json()["invites"])
    gen = client.post("/api/admin/invites?count=3&note=wave1", headers=H(admin_tok))
    assert gen.status_code == 200, gen.text
    assert gen.json()["created"] == 3 and len(gen.json()["codes"]) == 3
    listing = client.get("/api/admin/invites", headers=H(admin_tok)).json()["invites"]
    assert len(listing) == before + 3
    assert all(not i["used"] for i in listing if i["code"] in gen.json()["codes"])


def test_admin_feedback_list_and_filter(client, admin_tok):
    # Seed one bug report directly so the list + filter have content.
    from app.database import SessionLocal
    from app.models import Feedback
    db = SessionLocal()
    db.add(Feedback(kind="bug", message="audit bug", page="/app/jobs", severity="high", status="open"))
    db.commit(); db.close()

    allfb = client.get("/api/admin/feedback", headers=H(admin_tok))
    assert allfb.status_code == 200
    assert any(f["kind"] == "bug" and f["message"] == "audit bug" for f in allfb.json()["feedback"])

    bugs = client.get("/api/admin/feedback?kind=bug", headers=H(admin_tok)).json()["feedback"]
    assert bugs and all(f["kind"] == "bug" for f in bugs)


def test_admin_ops_requires_admin(client):
    # No token → unauthorized (not 200).
    assert client.get("/api/admin/metrics").status_code in (401, 403)
