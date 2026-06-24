"""SmartRecruiters — AUTO-APPLY-supported via public ATS API.

Discovery: app/jobs/providers/smartrecruiters.py (public postings API). Apply URL
is the genuine SmartRecruiters careers page. Classified auto-apply-supported.
"""
from __future__ import annotations
from . import AUTO_APPLIED

NAME = "SmartRecruiters"
DOMAIN = "smartrecruiters.com"
AUTO_APPLY = True
DISCOVERY_API = "https://api.smartrecruiters.com/v1/companies/{company}/postings"


def application_mode() -> str:
    return AUTO_APPLIED
