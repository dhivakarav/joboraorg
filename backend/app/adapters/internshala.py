"""Internshala adapter — MANUAL ONLY (Phase 1).

Internshala application submission is account-gated and not permitted via
automation (robots.txt disallows the relevant paths; no public API). Jobara
never auto-submits to Internshala — it prepares the user's details and the job
is marked "Manual Apply Required". Discovery is handled by the Internshala
provider when an authorized data source is configured.
"""
from __future__ import annotations

from .base import Adapter


class InternshalaAdapter(Adapter):
    platform = "Internshala"
    supports_prefill = True
    supports_auto_submit = False
    manual_only = True
    match_hosts = ("internshala.com",)
    match_sources = ("internshala",)
