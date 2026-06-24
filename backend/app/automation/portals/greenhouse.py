"""Greenhouse — AUTO-APPLY via public ATS API.

Discovery: app/jobs/providers/greenhouse.py (public board API).
Submission: app/adapters/greenhouse_production.py drives a real submission when
JOBORA_LIVE=1; otherwise the application is prepared/queued. application_mode =
"auto_applied".
"""
from __future__ import annotations
from . import AUTO_APPLIED

NAME = "Greenhouse"
DOMAIN = "greenhouse.io"
AUTO_APPLY = True
DISCOVERY_API = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


def application_mode() -> str:
    return AUTO_APPLIED
