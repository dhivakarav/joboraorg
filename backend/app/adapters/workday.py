"""Workday adapter — MANUAL ONLY.

Workday application flows are account-gated, multi-step, and protected by
anti-automation measures; programmatic submission is not reliably or lawfully
possible. Jobora prefills a package for the user's convenience but marks the job
"Manual Apply Required".
"""
from __future__ import annotations

from .base import Adapter


class WorkdayAdapter(Adapter):
    platform = "Workday"
    supports_prefill = True       # we can still prepare the data for the user
    supports_auto_submit = False
    manual_only = True
    match_hosts = ("myworkdayjobs.com", "workday.com", "wd1.myworkday", "wd3.myworkday", "wd5.myworkday")
    match_sources = ("workday",)
