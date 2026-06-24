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
    # Generic auto-submit stays False: the engine + base.submit() must NOT drive
    # Internshala (it has no credentials there, and unattended applies aren't
    # permitted). Real submission is the dedicated, credential-gated, opt-in
    # /jobs/internshala/apply path (Option B), advertised by the flag below.
    supports_auto_submit = False
    manual_only = True
    # Live auto-submission is possible ONLY via the dedicated path: the user's
    # own stored credentials + JOBORA_LIVE=1 + explicit per-application approval.
    supports_credential_submit = True
    match_hosts = ("internshala.com",)
    match_sources = ("internshala",)
