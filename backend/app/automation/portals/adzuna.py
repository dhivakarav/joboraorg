"""Adzuna — SEARCH via official API, then LINK (no auto-submit).

Discovery: app/jobs/providers/adzuna.py (official India API:
https://api.adzuna.com/v1/api/jobs/in/search). Adzuna returns a redirect apply
URL to the employer/aggregator — Jobora opens it for the user (Track & Apply);
it does NOT auto-submit. application_mode = "manual_link_provided".
"""
from __future__ import annotations
from . import MANUAL_LINK

NAME = "Adzuna"
DOMAIN = "adzuna.com"
AUTO_APPLY = False
SEARCH_API = "https://api.adzuna.com/v1/api/jobs/in/search"


def application_mode() -> str:
    return MANUAL_LINK
