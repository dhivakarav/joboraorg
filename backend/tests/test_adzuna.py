"""Adzuna provider: gating, official-API mapping, India-detection fix, and
India-first tier classification. All mocked — no real network, no key needed."""
import asyncio

from app.jobs import india
from app.jobs.providers.adzuna import AdzunaProvider


class _Resp:
    def __init__(self, payload): self._p = payload
    def raise_for_status(self): pass
    def json(self): return self._p


class _Client:
    """Minimal async client (no network)."""
    def __init__(self, payload): self._p, self.calls = payload, []
    async def get(self, url, params=None):
        self.calls.append({"url": url, "params": params})
        return _Resp(self._p)


def _ad(title, company, loc, desc="", smin=None, smax=None, cur=None, jid="1"):
    return {"id": jid, "title": title, "company": {"display_name": company},
            "location": {"display_name": loc}, "redirect_url": f"https://adzuna/{jid}",
            "salary_min": smin, "salary_max": smax, "salary_currency": cur,
            "description": desc, "created": "2026-06-01T00:00:00Z", "contract_time": ""}


def _fetch(country, payload):
    p = AdzunaProvider()
    p.app_id, p.app_key = "id", "key"   # _fetch_country only puts these in params
    return asyncio.run(p._fetch_country(_Client(payload), country, "engineer", 20))


# --- gating ----------------------------------------------------------------
def test_adzuna_gated(monkeypatch):
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
    assert AdzunaProvider().available() is False
    monkeypatch.setenv("ADZUNA_APP_ID", "a"); monkeypatch.setenv("ADZUNA_APP_KEY", "b")
    assert AdzunaProvider().available() is True


# --- mapping ---------------------------------------------------------------
def test_official_payload_mapping():
    job = _fetch("in", {"results": [_ad("Backend Engineer", "Infosys", "Bengaluru, Karnataka",
                                        smin=600000, smax=1200000, cur="INR")]})[0]
    assert job.source == "Adzuna" and job.company == "Infosys"
    assert job.apply_url == "https://adzuna/1" and job.is_valid()
    assert "600,000" in job.salary and "INR" in job.salary


# --- India detection (the G1 fix) + the 4 required scenarios ----------------
def test_india_onsite_region_only_is_tagged():
    # Region-only label "Karnataka" (no city) must still be detected as India.
    job = _fetch("in", {"results": [_ad("Software Engineer", "TCS", "Karnataka")]})[0]
    assert india._is_india(job.location)                 # tagged "Karnataka, India"
    assert job.remote is False
    assert india.india_tier(job.location, job.remote) == india.TIER_INDIA   # Tier 1


def test_india_onsite_city_and_country_styles():
    jobs = _fetch("in", {"results": [
        _ad("Data Scientist", "Zoho", "Bengaluru", jid="1"),         # city
        _ad("AI Engineer", "Wipro", "India", jid="2"),               # country word
        _ad("Backend Engineer", "Acme", "", jid="3"),                # blank → "India"
    ]})
    for j in jobs:
        assert india.india_tier(j.location, j.remote) == india.TIER_INDIA, j.location


def test_india_remote_is_tier2():
    job = _fetch("in", {"results": [_ad("Remote Software Engineer", "Razorpay", "Bengaluru")]})[0]
    assert job.remote is True
    assert india.india_tier(job.location, job.remote) == india.TIER_INDIA_REMOTE  # Tier 2


def test_us_remote_is_global_tier():
    job = _fetch("us", {"results": [_ad("Remote Backend Engineer", "Stripe", "San Francisco, CA")]})[0]
    assert job.remote is True
    assert india.india_tier(job.location, job.remote) == india.TIER_GLOBAL        # Tier 3


def test_europe_onsite_is_global_tier():
    job = _fetch("de", {"results": [_ad("Software Engineer", "SAP", "Berlin, Germany")]})[0]
    assert job.remote is False
    assert india.india_tier(job.location, job.remote) == india.TIER_GLOBAL        # Tier 3


# --- employment type (internship / fresher coverage) -----------------------
def test_employment_type_inference():
    jobs = _fetch("in", {"results": [
        _ad("Data Science Intern", "Acme", "Pune", jid="1"),
        _ad("Graduate Engineer Trainee", "Beta", "Chennai", jid="2"),
        _ad("Senior Backend Engineer", "Gamma", "Mumbai", jid="3"),
    ]})
    et = {j.title: j.employment_type for j in jobs}
    assert et["Data Science Intern"] == "internship"
    assert et["Graduate Engineer Trainee"] == "fresher"
    assert et["Senior Backend Engineer"] == "job"


# --- India-tier ranking with Adzuna jobs (requirement 4) -------------------
def test_adzuna_jobs_rank_india_first():
    india_jobs = _fetch("in", {"results": [_ad("Software Engineer", "Infosys", "Karnataka")]})
    us_jobs = _fetch("us", {"results": [_ad("Software Engineer", "Stripe", "San Francisco, CA")]})
    eu_jobs = _fetch("de", {"results": [_ad("Software Engineer", "SAP", "Berlin, Germany")]})
    mixed = us_jobs + eu_jobs + india_jobs            # India deliberately last
    mixed.sort(key=lambda j: india.india_tier(j.location, j.remote))
    assert mixed[0].company == "Infosys"              # India floats to the top
    assert india.india_tier(mixed[-1].location, mixed[-1].remote) == india.TIER_GLOBAL
