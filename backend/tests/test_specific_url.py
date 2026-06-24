"""Every row a user sees must link to a SPECIFIC job application page — never a
portal homepage, search-results page, or SEO category listing. These tests lock
in the `is_specific_job_url` gate used by both the /jobs endpoint and the
auto-apply engine."""
import pytest

from app.jobs.base import is_specific_job_url


SPECIFIC = [
    # ATS / board listings with a stable job id in the path
    "https://boards.greenhouse.io/robinhood/jobs/796068",
    "https://jobs.lever.co/company/abc-123",
    "https://www.arbeitnow.com/jobs/companies/nextexai/",
    "https://internshala.com/internship/detail/data-science-intern-12345",
    # SEO-slug listing that still carries real job ids (naukrigulf via JSearch)
    "https://www.naukrigulf.com/software-engineer-jobs-in-dubai-in-talabat-cd-20010198-jid-180626500007",
]

GENERIC = [
    "",                                                  # empty
    "https://example.com/",                              # bare homepage
    "http://localhost:8001/mock_internshala_feed.json",  # local mock feed
    "https://internshala.com/internships/",              # category page
    "https://www.naukri.com/software-jobs",              # plural category slug
    "https://gulfjobnest.com/software-engineer-jobs-in-dubai/",  # category, no id
    "https://www.linkedin.com/jobs/search/?keywords=python",     # search results
    "https://www.indeed.com/jobs?q=developer",           # search query
    "https://www.foundit.in/srp/results?query=engineer",  # results page
]


@pytest.mark.parametrize("url", SPECIFIC)
def test_specific_urls_pass(url):
    assert is_specific_job_url(url) is True


@pytest.mark.parametrize("url", GENERIC)
def test_generic_urls_rejected(url):
    assert is_specific_job_url(url) is False
