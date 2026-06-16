"""Internshala Phase 1 tests — discovery plumbing (NO auto-submission).

These exercise the lawful pieces: the provider is disabled without an authorized
source, stipend converts to INR, internship metadata flows, dedupe is stable,
employment-type filtering works, and the apply adapter is manual-only.
"""
from app.adapters import adapter_for
from app.jobs.base import RawJob, matches_filters
from app.jobs.providers.internshala import InternshalaProvider


def test_provider_disabled_without_authorized_source():
    p = InternshalaProvider()
    assert p.available() is False           # no INTERNSHALA_FEED_URL configured
    assert "robots" in p.unavailable_reason().lower()
    assert p.official_api is False


def test_feed_record_maps_to_rawjob_with_inr_stipend():
    # NOTE: this is a sample of the *documented feed contract* for a unit test —
    # not scraped or fabricated production data.
    rec = {
        "id": "abc123", "title": "Backend Development Intern", "company": "Acme",
        "type": "Internship", "stipend": "₹15,000 /month", "location": "Work From Home",
        "duration": "3 months", "apply_url": "https://internshala.com/internship/detail/abc123",
        "description": "Python, FastAPI internship",
    }
    job = InternshalaProvider()._to_rawjob(rec)
    d = job.to_dict()
    assert d["employment_type"] == "internship"
    assert d["duration"] == "3 months"
    assert d["remote"] is True               # "Work From Home" → remote
    assert d["salary_inr"]                    # stipend converted to INR display
    assert d["source"] == "Internshala"


def test_fresher_classification():
    job = InternshalaProvider()._to_rawjob(
        {"id": "f1", "title": "Fresher Software Engineer", "company": "X",
         "type": "Fresher Job", "apply_url": "https://internshala.com/job/detail/f1"})
    assert job.employment_type == "fresher"


def test_dedupe_fingerprint_stable():
    rec = {"id": "dup1", "title": "Intern", "company": "Y",
           "apply_url": "https://internshala.com/internship/detail/dup1"}
    a = InternshalaProvider()._to_rawjob(rec)
    b = InternshalaProvider()._to_rawjob(rec)
    assert a.fingerprint == b.fingerprint     # same record → same id → dedupe


def test_employment_type_filter():
    intern = RawJob(source="Internshala", title="Data Intern", company="Z",
                    apply_url="https://x", employment_type="internship")
    job = RawJob(source="Greenhouse", title="Senior Eng", company="Z",
                 apply_url="https://x", employment_type="job")
    assert matches_filters(intern, "", "", [], employment_type="internship")
    assert not matches_filters(job, "", "", [], employment_type="internship")
    assert matches_filters(job, "", "", [], employment_type="any")


def test_internshala_adapter_is_manual_only():
    a = adapter_for({"source": "Internshala", "apply_url": "https://internshala.com/internship/detail/x"})
    assert a.platform == "Internshala"
    assert a.manual_only is True and a.supports_auto_submit is False


# ---------------------------------------------------------------------------
# Feed-level fetch, no-scrape guard, India-first tiering, dedupe & analytics
# (licensed-feed path, fully mocked — never touches internshala.com)
# ---------------------------------------------------------------------------
import asyncio
import types

import pytest

import app.jobs.providers.internshala as ish
from app.jobs import india, coverage
from app.jobs.aggregator import _canonical_url


class _Resp:
    def __init__(self, p): self._p = p
    def raise_for_status(self): pass
    def json(self): return self._p


class _Client:
    def __init__(self, p): self._p, self.calls = p, []
    async def get(self, url, params=None):
        self.calls.append((url, params)); return _Resp(self._p)


_FEED = {"internships": [
    {"id": "1", "title": "Machine Learning Intern", "company": "Acme",
     "stipend": "₹15,000 /month", "location": "Bengaluru", "duration": "6 Months",
     "skills": ["Python", "Machine Learning"], "type": "internship",
     "url": "https://internshala.com/internship/detail/ml-intern-acme-1"},
    {"id": "2", "title": "Web Development Intern", "company_name": "Beta",
     "stipend": "₹10,000 /month", "location": "Work from home", "duration": "3 Months",
     "skills": "HTML, CSS, JavaScript", "type": "internship",
     "url": "https://internshala.com/internship/detail/web-2"},
]}


@pytest.fixture(autouse=True)
def _restore_feed_env():
    o_url, o_skip = ish.FEED_URL, ish.SKIP_ROBOTS
    yield
    ish.FEED_URL, ish.SKIP_ROBOTS = o_url, o_skip


def _fetch(payload, feed_url="https://feed.partner.example/internshala", trusted=True):
    ish.FEED_URL, ish.SKIP_ROBOTS = feed_url, trusted
    return asyncio.run(InternshalaProvider().fetch(_Client(payload), "intern", "India", 20))


def test_refuses_to_scrape_internshala_host():
    # A feed URL on internshala.com is refused unless explicitly trusted — the
    # provider never fetches Internshala HTML directly.
    assert _fetch(_FEED, feed_url="https://internshala.com/api/internships", trusted=False) == []


def test_feed_mapping_skills_and_india_tiers():
    jobs = _fetch(_FEED)
    assert len(jobs) == 2
    j1, j2 = jobs
    assert j1.duration == "6 Months" and "15,000" in j1.salary
    assert "Skills: Python, Machine Learning" in j1.description_snippet
    assert india.india_tier(j1.location, j1.remote) == india.TIER_INDIA          # Bengaluru on-site
    assert j2.company == "Beta"                                                    # company_name fallback
    assert j2.remote is True
    assert india.india_tier(j2.location, j2.remote) == india.TIER_INDIA_REMOTE    # work-from-home


def test_canonical_url_collapses_duplicates():
    a = _canonical_url("https://internshala.com/internship/detail/ml-intern-acme-1")
    b = _canonical_url("http://www.internshala.com/internship/detail/ml-intern-acme-1/?utm=google")
    assert a == b == "internshala.com/internship/detail/ml-intern-acme-1"


def _ns(source, url, et="internship", title="Software Engineer Intern", early=""):
    return types.SimpleNamespace(source=source, apply_url=url, employment_type=et,
                                 title=title, early_signal=early)


def test_is_internshala_detection():
    assert coverage.is_internshala_url("https://internshala.com/internship/detail/x")
    assert not coverage.is_internshala_url("https://stripe.com/jobs/1")
    assert coverage.is_internshala(_ns("JSearch", "https://internshala.com/x"))   # echo via JSearch
    assert coverage.is_internshala(_ns("Internshala", "https://x.com"))           # native source


def test_internshala_breakdown_counts():
    jobs = [
        _ns("Internshala", "https://internshala.com/internship/detail/1",
            title="Machine Learning Intern"),
        _ns("JSearch", "https://internshala.com/internship/detail/2",            # echo counts too
            title="Backend Developer Intern"),
        _ns("JSearch", "https://stripe.com/jobs/9", et="job", title="AI Engineer"),  # not Internshala
        _ns("Internshala", "https://internshala.com/x", et="fresher",
            title="Graduate Trainee", early="Fresher Friendly"),
    ]
    b = coverage.internshala_breakdown(jobs)
    assert b["internshala_total"] == 3          # 2 native + 1 JSearch echo
    assert b["internships"] == 2
    assert b["fresher"] == 1
    assert b["ai_ml"] == 1                       # "Machine Learning Intern"
    assert b["software"] == 1                    # "Backend Developer Intern"
