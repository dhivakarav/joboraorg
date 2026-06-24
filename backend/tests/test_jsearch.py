"""JSearch provider: gating, official-API mapping, eligibility/filter integration."""
import asyncio

from app.jobs.providers.jsearch import ENDPOINT, JSearchProvider


class _Resp:
    def __init__(self, payload, status_code=200, headers=None):
        self._p = payload
        self.status_code = status_code
        self.headers = headers or {"x-ratelimit-requests-remaining": "199"}
    def raise_for_status(self): pass
    def json(self): return self._p


class _Client:
    """Minimal async client capturing the request (no real network)."""
    def __init__(self, payload, boom=False):
        self._p, self.boom, self.calls = payload, boom, []
    async def get(self, url, params=None, headers=None):
        self.calls.append({"url": url, "params": params, "headers": headers})
        if self.boom:
            raise RuntimeError("network down")
        return _Resp(self._p)


PAYLOAD = {"status": "OK", "data": [
    {"job_id": "abc", "job_title": "Software Engineer Intern", "employer_name": "Acme",
     "job_apply_link": "https://acme.com/apply", "job_city": "Bengaluru", "job_country": "IN",
     "job_is_remote": True, "job_employment_type": "INTERN",
     "job_min_salary": 20000, "job_max_salary": 40000, "job_salary_currency": "INR",
     "job_salary_period": "MONTH", "job_posted_at_datetime_utc": "2026-06-01T00:00:00Z",
     "job_description": "Great early-career role"},
    {"job_id": "nourl", "job_title": "X", "employer_name": "Y", "job_apply_link": ""},  # dropped
]}


def test_available_is_gated(monkeypatch):
    monkeypatch.delenv("JSEARCH_API_KEY", raising=False)
    assert JSearchProvider().available() is False
    monkeypatch.setenv("JSEARCH_API_KEY", "rapid-key")
    assert JSearchProvider().available() is True


def test_fetch_maps_official_payload(monkeypatch):
    monkeypatch.setenv("JSEARCH_API_KEY", "rapid-key")
    p = JSearchProvider()
    c = _Client(PAYLOAD)
    jobs = asyncio.run(p.fetch(c, "software intern", "India", 40))

    # one valid job (the URL-less one is dropped)
    assert len(jobs) == 1
    j = jobs[0]
    assert j.source == "JSearch" and j.company == "Acme"
    assert j.apply_url == "https://acme.com/apply" and j.is_valid()
    assert j.employment_type == "internship"      # feeds the internship/new-grad filter
    assert j.remote is True
    assert "Bengaluru" in j.location               # India coverage
    assert j.external_id == "jsearch-abc"
    assert "INR" in j.salary

    # official API: hit the real endpoint with the RapidAPI auth headers (no scraping)
    call = c.calls[0]
    assert call["url"] == ENDPOINT
    assert call["headers"]["X-RapidAPI-Key"] == "rapid-key"
    assert call["headers"]["X-RapidAPI-Host"] == "jsearch.p.rapidapi.com"
    assert "software intern in India" in call["params"]["query"]


def test_fetch_isolates_errors(monkeypatch):
    monkeypatch.setenv("JSEARCH_API_KEY", "rapid-key")
    jobs = asyncio.run(JSearchProvider().fetch(_Client(PAYLOAD, boom=True), "x", "", 10))
    assert jobs == []   # a failing provider yields nothing, never raises


def test_registered_and_eligibility_internship_signal(monkeypatch):
    # Registered in the provider list...
    from app.jobs.providers import ALL_PROVIDERS
    assert any(p.name == "JSearch" for p in ALL_PROVIDERS)

    # ...and a JSearch internship row flows through eligibility + the early signal.
    monkeypatch.setenv("JSEARCH_API_KEY", "rapid-key")
    j = asyncio.run(JSearchProvider().fetch(_Client(PAYLOAD), "intern", "India", 5))[0]
    from app.jobs.eligibility import eligibility, early_signal
    student = {"seeker_type": "student", "experience": 0}
    d = j.to_dict()
    elig = eligibility(d, student)
    assert elig["eligible"] is True and elig["eligibility_tier"] in ("Excellent Match", "Good Match")
    assert early_signal(d) == "Internship"   # survives the internships-only hard filter
