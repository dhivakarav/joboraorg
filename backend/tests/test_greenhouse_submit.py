"""Greenhouse real-submit flow: read-only question fetch + the gated apply endpoint.
Board-API fetch and the background enqueue are stubbed (no network, no worker)."""
import io

import pytest

from app.adapters.greenhouse_fill import GHField


def _pdf():
    txt = "GH Tester gh@example.com Python"
    stream = f"BT /F1 11 Tf 50 760 Td ({txt}) Tj ET"
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    pdf = "%PDF-1.4\n"; offs = []
    for i, o in enumerate(objs, 1):
        offs.append(len(pdf)); pdf += f"{i} 0 obj\n{o}\nendobj\n"
    x = len(pdf); pdf += f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n"
    for o in offs:
        pdf += f"{o:010d} 00000 n \n"
    pdf += f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF"
    return pdf.encode("latin-1")


CANNED = ("Software Engineer Intern", [
    GHField("first_name", "input_text", "First Name", True, []),     # core → excluded
    GHField("email", "input_text", "Email", True, []),               # core → excluded
    GHField("resume", "input_file", "Resume", True, []),             # excluded
    GHField("question_1", "textarea", "Why do you want this role?", True, []),
    GHField("question_2", "multi_value_single_select", "Work authorization?", True,
            [("Yes", "y"), ("No", "n")]),
    GHField("question_3", "input_text", "LinkedIn", False, []),
])


@pytest.fixture(scope="session")
def gh_token(client):
    from app.database import SessionLocal
    from app.models import User
    from app.security import hash_password, issue_tokens
    db = SessionLocal()
    try:
        email = "gh_user@example.com"
        u = db.query(User).filter_by(email=email).first()
        if not u:
            u = User(full_name="GH Tester", email=email, hashed_password=hash_password("GhTest123"),
                     phone="+91 98765 43210", status="approved", is_admin=False,
                     seeker_type="student", email_verified=True)
            db.add(u); db.commit(); db.refresh(u)
        return issue_tokens(u)["access_token"]
    finally:
        db.close()


def H(t):
    return {"Authorization": f"Bearer {t}"}


GH_JOB = {"fingerprint": "gh-sub-1", "external_id": "gh-acme-123", "source": "Greenhouse",
          "title": "Software Engineer Intern", "company": "Acme",
          "apply_url": "https://boards.greenhouse.io/acme/jobs/123"}


def test_greenhouse_form_returns_required_questions(client, gh_token, monkeypatch):
    monkeypatch.setattr("app.routers.jobs.fetch_fields", lambda b, j: CANNED)
    r = client.post("/api/jobs/greenhouse/form", json=GH_JOB, headers=H(gh_token))
    assert r.status_code == 200, r.text
    body = r.json()
    req_names = {q["name"] for q in body["required_questions"]}
    opt_names = {q["name"] for q in body["optional_questions"]}
    assert req_names == {"question_1", "question_2"}          # required screening Qs
    assert opt_names == {"question_3"}                        # optional kept separately
    assert "first_name" not in req_names and "resume" not in req_names  # core/file excluded
    # the select carries its options for the UI
    q2 = next(q for q in body["required_questions"] if q["name"] == "question_2")
    assert {"label": "Yes", "value": "y"} in q2["values"]


def test_greenhouse_apply_requires_approval(client, gh_token):
    r = client.post("/api/jobs/greenhouse/apply", headers=H(gh_token),
                    json={**GH_JOB, "answers": {}, "approved": False})
    assert r.status_code == 400
    msg = (r.json().get("error") or r.json().get("detail") or "").lower()
    assert "approve" in msg


def test_greenhouse_apply_rejects_non_greenhouse(client, gh_token):
    r = client.post("/api/jobs/greenhouse/apply", headers=H(gh_token),
                    json={**GH_JOB, "source": "Lever", "approved": True})
    assert r.status_code == 400


def test_greenhouse_apply_valid_enqueues(client, gh_token, monkeypatch):
    # give the user a real resume so profile_complete passes
    up = client.post("/api/resume/upload", headers=H(gh_token),
                     files={"file": ("r.pdf", io.BytesIO(_pdf()), "application/pdf")})
    assert up.status_code == 200, up.text
    # stub the background enqueue so no worker/browser runs
    monkeypatch.setattr("app.routers.jobs.enqueue_submission", lambda app_id: "test-queue")

    r = client.post("/api/jobs/greenhouse/apply", headers=H(gh_token),
                    json={**GH_JOB, "answers": {"question_1": "I'm keen", "question_2": "y"},
                          "approved": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["submission_status"] == "Queued"
    assert body["queue_backend"] == "test-queue"
    assert isinstance(body["application_id"], int)


# --- regression: company-careers-domain gh_jid URLs resolve to the embed form,
#     and a truly unmappable URL yields None (caller fails safe, never crashes goto).
def test_resolve_form_url_from_company_domain_gh_jid():
    from app.adapters.greenhouse_production import resolve_form_url
    # Coinbase / Druva apply pages live on the company's own domain with ?gh_jid=.
    assert resolve_form_url({"apply_url": "https://www.coinbase.com/careers/positions/7558051?gh_jid=7558051"}) \
        == "https://boards.greenhouse.io/embed/job_app?token=7558051"
    assert resolve_form_url({"apply_url": "https://www.druva.com/careers/jobs/8207141002/?gh_jid=8207141002"}) \
        == "https://boards.greenhouse.io/embed/job_app?token=8207141002"


def test_resolve_form_url_none_for_unmappable():
    from app.adapters.greenhouse_production import resolve_form_url
    # No gh_jid, not a greenhouse domain → None (apply() then fails safe as Manual).
    assert resolve_form_url({"apply_url": "https://acme.example.com/careers/apply"}) is None


def test_apply_guard_no_crash_on_empty_form_url():
    import asyncio
    from app.adapters.greenhouse_production import apply, S_MANUAL
    out = asyncio.run(apply("", [], {"name": "A B", "email": "a@b.co", "phone": "1"},
                            "", {}, "/tmp", tag="apply"))
    assert out.submission_status == S_MANUAL          # graceful, not an exception
    assert "form" in (out.failure_reason or "").lower()
