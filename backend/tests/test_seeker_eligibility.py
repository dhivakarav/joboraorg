"""The auto-apply engine must treat a student/fresher as early-career via their
explicit seeker_type — not only the years_experience<=2 proxy — so senior/staff
roles are excluded from the auto-queue. Safety-critical: this decides which roles
the engine will attempt to auto-submit to.

Logic under test (eligibility._is_early): early-career if
    seeker_type in {student, fresher}  OR  years_experience <= 2
Both signals are kept; neither silently overrides the other.
"""
import time

from app.jobs.eligibility import eligibility, internships_only_default

_SENIOR_JOB = {"title": "Senior Staff Software Engineer", "company": "Acme",
               "description_snippet": "10+ years experience required", "location": "India"}
_JUNIOR_JOB = {"title": "Software Engineer", "company": "Acme",
               "description_snippet": "entry level", "location": "India"}


def _profile(seeker_type="", experience=0):
    return {"skills": ["python"], "roles": ["software engineer"], "keywords": [],
            "experience": experience, "seeker_type": seeker_type}


# ---- explicit seeker_type signal (the new path the engine now feeds) -----------
def test_student_with_high_experience_is_early_career():
    # seeker_type wins via the OR even though years_experience > 2.
    p = _profile(seeker_type="student", experience=5)
    assert eligibility(_SENIOR_JOB, p)["eligible"] is False   # senior role excluded
    assert internships_only_default(p) is True


def test_fresher_is_early_career():
    p = _profile(seeker_type="fresher", experience=8)
    assert eligibility(_SENIOR_JOB, p)["eligible"] is False


# ---- years_experience fallback (preserved for missing/blank seeker_type) -------
def test_fallback_low_experience_is_early_when_seeker_unset():
    p = _profile(seeker_type="", experience=1)
    assert eligibility(_SENIOR_JOB, p)["eligible"] is False   # early via fallback
    assert internships_only_default(p) is False               # no seeker_type → off


def test_experienced_user_keeps_senior_eligibility():
    # Not early by either signal → senior roles remain eligible.
    p = _profile(seeker_type="experienced", experience=8)
    assert eligibility(_SENIOR_JOB, p)["eligible"] is True


# ---- the engine actually passes seeker_type into the profile it scores against --
def test_engine_load_context_includes_seeker_type(client):  # client → app/DB tables ready
    from app.database import SessionLocal
    from app.models import User
    from app.security import hash_password
    from app.automation import engine

    db = SessionLocal()
    try:
        u = User(full_name="Seeker", email=f"seek{int(time.time()*1e6)}@example.com",
                 hashed_password=hash_password("x"), status="approved",
                 seeker_type="student", years_experience=5)
        db.add(u); db.commit(); uid = u.id
    finally:
        db.close()

    ctx = engine._load_context(uid)
    assert ctx["profile"]["seeker_type"] == "student"   # explicit signal is plumbed in
    # and a senior role would be excluded for this profile
    assert eligibility(_SENIOR_JOB, ctx["profile"])["eligible"] is False
