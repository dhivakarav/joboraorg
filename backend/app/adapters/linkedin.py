"""LinkedIn adapter — MANUAL ONLY.

Automated application/scraping with stored credentials violates LinkedIn's Terms
of Service and is actively blocked. Jobora never auto-submits to LinkedIn. The
job is always marked "Manual Apply Required"; we still prepare the profile data
so the user can paste/upload quickly.
"""
from __future__ import annotations

from .base import Adapter


class LinkedInAdapter(Adapter):
    platform = "LinkedIn"
    supports_prefill = True
    supports_auto_submit = False
    manual_only = True
    match_hosts = ("linkedin.com",)
    match_sources = ("linkedin",)
