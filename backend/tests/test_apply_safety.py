"""Safety regressions:
  1. A submit is "Submitted" ONLY with positive confirmation proof — reaching a
     job-description/Apply page must NOT count as submitted.
  2. "Start Applying" queues auto-apply jobs as 'Pending Approval' and never
     submits to a real company without explicit approval.
"""
import io

from app.adapters.playwright_fill import _is_confirmed
from app.status import display_status


class _App:
    def __init__(self, **kw):
        self.submission_status = kw.get("ss", "")
        self.status = kw.get("legacy", "Tracked")
        self.manual_required = kw.get("manual", False)
        self.application_id = kw.get("app_id", "")
        self.external_application_id = ""
        self.confirmation_url = kw.get("conf", "")
        self.evidence_available = kw.get("evid", False)


# ---- 1. false-positive "Submitted" fix --------------------------------------
def test_description_page_is_not_confirmed():
    # The exact failure mode we saw: real Greenhouse job description page.
    body = ("Back to jobs\nSenior Fullstack Software Engineer\nSan Francisco\n"
            "Apply\nWho Are We?\nPostman is the world's leading API platform...")
    assert _is_confirmed(body) is False          # no proof → NOT submitted


def test_real_confirmation_is_confirmed():
    assert _is_confirmed("Thank you! Your application has been received.") is True
    assert _is_confirmed("Application submitted. Application ID: GH-7F3K9") is True


def test_pending_approval_display_status():
    app = _App(ss="Pending Approval")
    assert display_status(app) == "Pending Approval"


# ---- 2. approval gate end-to-end -------------------------------------------
def _approved_user_token():
    import time
    from app.database import SessionLocal
    from app.models import User
    from app.security import hash_password, issue_tokens
    db = SessionLocal()
    try:
        u = User(full_name="Approver", email=f"approve{int(time.time()*1000)}@example.com",
                 hashed_password=hash_password("x"), status="approved", seeker_type="fresher")
        db.add(u); db.commit(); db.refresh(u)
        return u.id, issue_tokens(u)["access_token"]
    finally:
        db.close()


def test_pending_approval_requires_explicit_confirm(client, monkeypatch):
    # stub the background enqueue so no worker/browser runs in the test loop
    monkeypatch.setattr("app.routers.apply.enqueue_submission", lambda app_id: "test-queue")
    uid, tok = _approved_user_token()
    H = {"Authorization": f"Bearer {tok}"}

    # Simulate what Start Applying records for an auto-capable job: Pending Approval.
    from app.database import SessionLocal
    from app.models import Application
    db = SessionLocal()
    app = Application(user_id=uid, portal="Greenhouse", source="Greenhouse",
                     platform="Greenhouse", job_title="ML Engineer", company="Acme",
                     apply_url="https://boards.greenhouse.io/acme/jobs/1", match_score=72,
                     job_url_hash="pa-test-1", status="Pending", submission_status="Pending Approval")
    db.add(app); db.commit(); aid = app.id; db.close()

    # It shows up as awaiting approval, and is NOT submitted.
    pend = client.get("/api/apply/pending", headers=H).json()
    assert any(i["id"] == aid for i in pend["items"])
    assert pend["live_ready"] is False           # JOBORA_LIVE=0 in tests

    # Approving with live OFF must NOT silently submit — it cannot become Submitted.
    r = client.post("/api/apply/approve", headers=H, json={"application_ids": [aid]})
    assert r.status_code == 200 and r.json()["approved"] == 1
    # After approval with live off, the queue marks it Manual Apply Required — never Submitted/Verified.
    apps = client.get("/api/applications?page=1&page_size=50", headers=H).json()["items"]
    row = next(a for a in apps if a["id"] == aid)
    assert row["display_status"] != "Verified Submitted"
    assert row["display_status"] != "Submitted"
