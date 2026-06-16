"""Wellfound adapter — MANUAL ONLY.

Wellfound applications are account-gated and not permitted via automation (no
public API; robots.txt disallows the job paths). Jobora never auto-submits to
Wellfound — it prepares the user's details and marks the job "Manual Apply
Required". Discovery is handled by the Wellfound provider when an authorized
data source is configured.
"""
from __future__ import annotations

from .base import Adapter


class WellfoundAdapter(Adapter):
    platform = "Wellfound"
    supports_prefill = True
    supports_auto_submit = False
    manual_only = True
    match_hosts = ("wellfound.com", "angel.co")
    match_sources = ("wellfound",)
