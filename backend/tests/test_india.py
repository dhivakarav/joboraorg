"""India-first discovery: pure signal/filter helpers + the /jobs filter & ranking
wiring (company / min_salary / duration + India & priority-domain boost)."""
import pytest

from app.jobs import india


# ----------------------------------------------------------------------------
# 1. Pure helpers
# ----------------------------------------------------------------------------
def test_india_bonus_hub_beats_remote_beats_nothing():
    assert india.india_bonus("Bangalore, India") > india.india_bonus("Remote", True)
    assert india.india_bonus("Remote", True) > india.india_bonus("London, UK")
    assert india.india_bonus("Chennai") == india.india_bonus("Hyderabad")  # all hubs equal


def test_is_india_location():
    assert india.is_india_location("Pune, Maharashtra")
    assert india.is_india_location("Remote - India", remote=True)
    assert not india.is_india_location("Berlin, Germany")
    assert not india.is_india_location("Remote", remote=True)  # generic remote ≠ India


def test_domain_bonus_priority_titles():
    for t in ["Machine Learning Intern", "Data Scientist", "Backend Engineer",
              "Full Stack Developer", "AI/ML Engineer", "SDE Intern", "Software Engineer"]:
        assert india.domain_bonus(t) > 0, t
    assert india.domain_bonus("Marketing Associate") == 0
    assert india.domain_bonus("HR Intern") == 0


def test_company_match_substring_ci():
    assert india.company_match("Razorpay Software", "razorpay")
    assert india.company_match("Zoho Corp", "ZOHO")
    assert not india.company_match("Acme", "globex")
    assert india.company_match("Anything", "")  # empty filter matches all


@pytest.mark.parametrize("text,expected", [
    ("₹3 L", 300_000),
    ("₹1.75 Cr", 17_500_000),
    ("₹6L - ₹10L", 600_000),          # first figure
    ("₹20,000/month", 240_000),       # annualized
    ("12,00,000", 1200000),           # plain rupees (no grouping assumptions)
    ("", None),
    ("competitive", None),
])
def test_salary_inr_annual(text, expected):
    assert india.salary_inr_annual(text) == expected


def test_passes_salary_keeps_unknown():
    assert india.passes_salary("", 600_000)            # unknown salary kept
    assert india.passes_salary("₹10 L", 600_000)       # 10L >= 6L
    assert not india.passes_salary("₹3 L", 600_000)    # 3L < 6L
    assert india.passes_salary("₹3 L", 0)              # no floor → keep


def test_duration_match_keeps_unknown():
    assert india.duration_match("6 months", "6")
    assert not india.duration_match("6 months", "3")
    assert india.duration_match("", "3")               # unknown duration kept
    assert india.duration_match("anything", "")        # no filter → keep


def test_india_recognizes_iso_country_code():
    # Google for Jobs / JSearch emit "City, State, IN" or bare "IN" — never "india".
    for loc in ["Mumbai, Maharashtra, IN", "Bengaluru, Karnataka, IN", "IN",
                "Andhra Pradesh, IN"]:
        assert india._is_india(loc), loc
        assert india.india_bonus(loc) == 25.0, loc      # ranking boost applies
    assert not india._is_india("San Francisco, CA")
    assert not india._is_india("Berlin, Germany")


def test_india_location_filter_matches_iso_jobs():
    # The exact bug: filter "India" must match a "…, IN" job (it didn't before).
    assert india.india_location_matches("india", "Mumbai, Maharashtra, IN")
    assert india.india_location_matches("india", "IN")
    assert not india.india_location_matches("india", "New York, NY")


def test_city_aliases_bangalore_bengaluru():
    assert india.india_location_matches("bangalore", "Bengaluru, Karnataka, IN")
    assert india.india_location_matches("bengaluru", "Bangalore, IN")
    assert india.india_location_matches("delhi ncr", "Gurugram, Haryana, IN")
    assert not india.india_location_matches("chennai", "Pune, Maharashtra, IN")


def test_remote_india_matches_remote_and_india():
    assert india.india_location_matches("remote india", "Remote", remote=True)
    assert india.india_location_matches("remote india", "Hyderabad, IN")
    assert not india.india_location_matches("remote india", "London, UK")


def test_is_india_filter_classification():
    assert india.is_india_filter("India") and india.is_india_filter("Remote India")
    assert india.is_india_filter("Bangalore") and india.is_india_filter("Delhi NCR")
    assert not india.is_india_filter("Dubai") and not india.is_india_filter("Remote")


def test_matches_filters_india_keeps_iso_drops_us():
    # End-to-end through the aggregator's relevance filter (the real drop point).
    from app.jobs.base import RawJob, matches_filters
    ind = RawJob(source="JSearch", title="AI/ML Intern", company="Linde",
                 location="Mumbai, Maharashtra, IN", apply_url="https://x/1")
    us = RawJob(source="Greenhouse", title="AI/ML Intern", company="Stripe",
                location="San Francisco, CA", apply_url="https://x/2")
    assert matches_filters(ind, "", "India", [])          # kept (was wrongly dropped)
    assert not matches_filters(us, "", "India", [])       # US correctly filtered out


# ----------------------------------------------------------------------------
# 2. /jobs endpoint — filters + India/domain ranking (aggregator stubbed)
# ----------------------------------------------------------------------------
def H(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="session")
def india_token(client):
    from app.database import SessionLocal
    from app.models import User
    from app.security import hash_password, issue_tokens
    db = SessionLocal()
    try:
        email = "india_user@example.com"
        u = db.query(User).filter_by(email=email).first()
        if not u:
            u = User(full_name="India User", email=email,
                     hashed_password=hash_password("UserTest123"), status="approved",
                     is_admin=False, seeker_type="student", years_experience=0,
                     email_verified=True)
            db.add(u); db.commit(); db.refresh(u)
        return issue_tokens(u)["access_token"]
    finally:
        db.close()


def _job(**kw):
    base = dict(fingerprint="fp", external_id="x", source="JSearch",
                title="Software Engineer Intern", company="Acme",
                location="Bangalore, India", salary="", salary_inr="",
                deadline="", posted_at="", remote=False, job_type="",
                employment_type="internship", duration="", apply_url="https://x/job",
                description_snippet="", verified=False)
    base.update(kw)
    base["fingerprint"] = base["fingerprint"] + base["company"] + base["title"]
    return base


def _stub(monkeypatch, jobs):
    async def fake_search(**kwargs):
        return list(jobs)
    monkeypatch.setattr("app.routers.jobs.aggregator.search", fake_search)


def test_company_filter(client, india_token, monkeypatch):
    _stub(monkeypatch, [_job(company="Razorpay"), _job(company="Globex")])
    r = client.get("/api/jobs?internships_only=false&company=razorpay", headers=H(india_token))
    assert r.status_code == 200, r.text
    companies = {j["company"] for j in r.json()["items"]}
    assert companies == {"Razorpay"}


def test_min_salary_filter_keeps_unknown(client, india_token, monkeypatch):
    _stub(monkeypatch, [
        _job(company="Hi", salary_inr="₹12 L"),
        _job(company="Lo", salary_inr="₹3 L"),
        _job(company="Unknown", salary_inr=""),
    ])
    r = client.get("/api/jobs?internships_only=false&min_salary=600000", headers=H(india_token))
    companies = {j["company"] for j in r.json()["items"]}
    assert "Hi" in companies and "Unknown" in companies   # >=6L and unknown kept
    assert "Lo" not in companies                           # 3L dropped


def test_duration_filter(client, india_token, monkeypatch):
    _stub(monkeypatch, [
        _job(company="Six", duration="6 months"),
        _job(company="Three", duration="3 months"),
        _job(company="NoDur", duration=""),
    ])
    r = client.get("/api/jobs?internships_only=false&duration=3", headers=H(india_token))
    companies = {j["company"] for j in r.json()["items"]}
    assert companies == {"Three", "NoDur"}                 # 6-month dropped, unknown kept


def test_india_and_domain_ranking(client, india_token, monkeypatch):
    _stub(monkeypatch, [
        _job(company="Far", title="Marketing Intern", location="London, UK"),
        _job(company="Hub", title="Machine Learning Intern", location="Chennai, India"),
    ])
    r = client.get("/api/jobs?internships_only=false", headers=H(india_token))
    items = r.json()["items"]
    assert items[0]["company"] == "Hub"  # India hub + priority domain ranks first


def test_remote_filter_keeps_only_remote(client, india_token, monkeypatch):
    _stub(monkeypatch, [
        _job(company="Onsite", location="Bangalore, India", remote=False),
        _job(company="RemoteCo", location="Bangalore, India", remote=True),
    ])
    r = client.get("/api/jobs?internships_only=false&remote=true", headers=H(india_token))
    companies = {j["company"] for j in r.json()["items"]}
    assert companies == {"RemoteCo"}


def test_india_remote_excludes_generic_worldwide_remote(client, india_token, monkeypatch):
    # location=India + remote=true → only India-tagged / Remote-India roles;
    # generic worldwide remote (location "Remote"/blank, no India tag) is excluded.
    _stub(monkeypatch, [
        _job(company="GenericRemote", location="Remote", remote=True),
        _job(company="BlankRemote", location="", remote=True),
        _job(company="USRemote", location="San Francisco, CA", remote=True),
        _job(company="RemoteIndia", location="Remote, India", remote=True),
        _job(company="HydIndia", location="Hyderabad, India", remote=True),
        _job(company="PuneOnsite", location="Pune, India", remote=False),
    ])
    r = client.get("/api/jobs?internships_only=false&location=India&remote=true",
                   headers=H(india_token))
    companies = {j["company"] for j in r.json()["items"]}
    assert companies == {"RemoteIndia", "HydIndia"}      # India remote only
    assert "GenericRemote" not in companies              # worldwide remote excluded
    assert "BlankRemote" not in companies
    assert "USRemote" not in companies
    assert "PuneOnsite" not in companies                 # not remote


# ----------------------------------------------------------------------------
# 3. India-first tiered ranking (Tier 1 India → Tier 2 India-remote → Tier 3 global)
# ----------------------------------------------------------------------------
from app.schemas import JobOut
from app.routers.jobs import _rank_key


def _jobout(company, location, remote, match=50, elig=90, title="Software Engineer"):
    return JobOut(fingerprint=company, source="S", title=title, company=company,
                  location=location, apply_url="http://x", remote=remote,
                  match_score=match, eligibility_score=elig)


def _ranked(jobs):
    """Apply the exact production sort key (tier primary, _rank_key secondary)."""
    return [j.company for j in sorted(
        jobs, key=lambda j: (india.india_tier(j.location, j.remote), -_rank_key(j)))]


def test_india_tier_classification():
    assert india.india_tier("Bengaluru, India", False) == india.TIER_INDIA
    assert india.india_tier("Hyderabad, IN", False) == india.TIER_INDIA
    assert india.india_tier("Remote, India", True) == india.TIER_INDIA_REMOTE
    assert india.india_tier("Hyderabad, IN", True) == india.TIER_INDIA_REMOTE
    assert india.india_tier("San Francisco, CA", False) == india.TIER_GLOBAL
    assert india.india_tier("Remote", True) == india.TIER_GLOBAL        # generic remote = global
    assert india.india_tier("Berlin, Germany", False) == india.TIER_GLOBAL
    assert india.TIER_INDIA < india.TIER_INDIA_REMOTE < india.TIER_GLOBAL


def test_india_always_ranks_above_us_even_with_higher_us_match():
    india_job = _jobout("Razorpay", "Bengaluru, India", False, match=10)
    us_job = _jobout("Stripe", "San Francisco, CA", False, match=99)   # far better match
    assert _ranked([us_job, india_job])[0] == "Razorpay"               # India still wins (tier)


def test_india_remote_ranks_above_us_remote():
    india_remote = _jobout("GitLabIN", "Remote, India", True, match=10)
    us_remote = _jobout("NotionUS", "Remote, US", True, match=99)
    order = _ranked([us_remote, india_remote])
    assert order[0] == "GitLabIN" and order[1] == "NotionUS"


def test_tier_order_india_then_india_remote_then_global():
    onsite = _jobout("INOnsite", "Pune, India", False)
    remote = _jobout("INRemote", "Remote, India", True)
    glob = _jobout("USGlobal", "New York, NY", False)
    assert _ranked([glob, remote, onsite]) == ["INOnsite", "INRemote", "USGlobal"]


def test_match_score_ordering_unchanged_within_tier():
    # Same tier (all India on-site), equal eligibility → higher match ranks first.
    a = _jobout("A", "Bengaluru, India", False, match=80)
    b = _jobout("B", "Chennai, India", False, match=40)
    c = _jobout("C", "Pune, India", False, match=60)
    assert _ranked([b, a, c]) == ["A", "C", "B"]                       # 80 > 60 > 40


def test_match_ordering_within_global_tier():
    a = _jobout("HiUS", "San Francisco, CA", False, match=90)
    b = _jobout("LoUS", "New York, NY", False, match=30)
    assert _ranked([b, a]) == ["HiUS", "LoUS"]                         # match order intact


def test_location_india_drops_us_remote_keeps_india_remote():
    # The reported bug fix at the layer that owns location: location=India must
    # exclude a US *remote* role (location wins over remote), keep India remote.
    from app.jobs.base import RawJob, matches_filters
    us_remote = RawJob(source="Ashby", title="Software Engineer", company="Notion",
                       location="San Francisco, California", remote=True, apply_url="https://x/1")
    in_remote = RawJob(source="Greenhouse", title="Software Engineer", company="Gitlab",
                       location="Remote, India", remote=True, apply_url="https://x/2")
    assert not matches_filters(us_remote, "", "India", [])   # US remote excluded
    assert matches_filters(in_remote, "", "India", [])       # India remote kept
