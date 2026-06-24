"""The Activity Log Stage dropdown must reflect the user's SAVED stage faithfully
for all 6 options — independent of submission_status (which masked Saved/Skipped/
Tracked before). `pipeline_stage` is returned per row and the UI renders it directly.
"""
import time

import pytest

from app.database import SessionLocal
from app.models import Application, User
from app.security import hash_password, issue_tokens
from app.status import USER_SETTABLE_STAGES


def _user():
    db = SessionLocal()
    try:
        u = User(full_name="Stage Tester", email=f"stage{int(time.time()*1e6)}@example.com",
                 hashed_password=hash_password("x"), status="approved", seeker_type="fresher")
        db.add(u); db.commit(); db.refresh(u)
        return u.id, issue_tokens(u)["access_token"]
    finally:
        db.close()


def _manual_row(uid):
    """A row whose submission_status is 'Manual Apply' — the case that used to mask
    Saved/Skipped/Tracked in the dropdown."""
    db = SessionLocal()
    try:
        a = Application(user_id=uid, portal="Naukri", source="Naukri", platform="Naukri",
                        job_title="SWE", company="Acme", apply_url="https://example.com/jobs/1",
                        match_score=70, job_url_hash=f"stage-{time.time()}",
                        status="Pending", submission_status="Manual Apply")
        db.add(a); db.commit(); db.refresh(a)
        return a.id
    finally:
        db.close()


@pytest.mark.parametrize("stage", sorted(USER_SETTABLE_STAGES))
def test_all_six_stages_round_trip(client, stage):
    uid, tok = _user()
    H = {"Authorization": f"Bearer {tok}"}
    aid = _manual_row(uid)

    # set the stage
    r = client.patch(f"/api/applications/{aid}/status", headers=H, json={"status": stage})
    assert r.status_code == 200, r.text

    # re-fetch (simulating a page refresh) and confirm the dropdown value persists
    items = client.get("/api/applications?page_size=100", headers=H).json()["items"]
    row = next(i for i in items if i["id"] == aid)
    assert row["pipeline_stage"] == stage          # ← faithfully reflects the saved stage


def test_submission_status_column_unaffected(client):
    """Setting a non-pipeline stage (Saved) must NOT change submission_status, and
    display_status still surfaces the submission state for that column."""
    uid, tok = _user()
    H = {"Authorization": f"Bearer {tok}"}
    aid = _manual_row(uid)

    client.patch(f"/api/applications/{aid}/status", headers=H, json={"status": "Saved"})
    row = next(i for i in client.get("/api/applications?page_size=100", headers=H).json()["items"]
               if i["id"] == aid)
    assert row["pipeline_stage"] == "Saved"            # stage dropdown shows Saved
    assert row["submission_status"] == "Manual Apply"  # submission column unchanged
    assert row["display_status"] == "Manual Apply"     # status badge still submission-derived


def test_unset_stage_is_empty(client):
    """A row with no user-set stage reports an empty pipeline_stage (— set stage —)."""
    uid, tok = _user()
    H = {"Authorization": f"Bearer {tok}"}
    aid = _manual_row(uid)
    row = next(i for i in client.get("/api/applications?page_size=100", headers=H).json()["items"]
               if i["id"] == aid)
    assert row["pipeline_stage"] == ""                 # "Pending" lifecycle hint is NOT a stage
