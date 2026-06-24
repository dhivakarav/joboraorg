"""Workable provider: public, token-free widget API mapping (no network in tests).

Verifies the provider is keyless/available, maps the widget payload to RawJob
correctly, and yields specific apply URLs.
"""
import asyncio

from app.jobs.base import is_specific_job_url
from app.jobs.providers.workable import WorkableProvider

PAYLOAD = {
    "name": "Zego",
    "description": "...",
    "jobs": [
        {
            "title": "Backend Engineer",
            "shortcode": "ABC123",
            "employment_type": "Full-time",
            "telecommuting": True,
            "department": "Engineering",
            "function": "Software Development",
            "industry": "Insurance",
            "application_url": "https://apply.workable.com/j/ABC123/apply",
            "published_on": "2026-06-20",
            "city": "London", "state": "England", "country": "United Kingdom",
        },
        {  # URL-less job is dropped
            "title": "No URL Role", "shortcode": "X", "application_url": "", "shortlink": "", "url": "",
        },
    ],
}


class _Resp:
    def __init__(self, payload): self._p = payload
    def raise_for_status(self): pass
    def json(self): return self._p


class _Client:
    def __init__(self, payload): self._p = payload
    async def get(self, url, headers=None, params=None):
        return _Resp(self._p)


def test_keyless_and_available():
    p = WorkableProvider()
    assert p.requires_key is False
    assert p.available() is True
    assert p.status() == "Connected"


def test_maps_widget_payload():
    p = WorkableProvider()
    p.accounts = ["zego"]   # one account
    jobs = asyncio.run(p.fetch(_Client(PAYLOAD), "engineer", "India", 50))

    assert len(jobs) == 1                     # the URL-less job is dropped
    j = jobs[0]
    assert j.company == "Zego"                # account display name, not the slug
    assert j.title == "Backend Engineer"
    assert j.apply_url == "https://apply.workable.com/j/ABC123/apply"
    assert is_specific_job_url(j.apply_url)   # a specific apply page, not a search
    assert j.remote is True                   # telecommuting → remote
    assert j.location == "London, England, United Kingdom"
    assert j.posted_at == "2026-06-20"
    # description signal is synthesised from structured fields (widget has no body)
    assert "Engineering" in j.description_snippet
