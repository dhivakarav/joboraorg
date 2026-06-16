"""Lever adapter — prefill + (opt-in) auto-submit."""
from __future__ import annotations

from .base import Adapter
from .playwright_fill import autofill_and_submit

SELECTORS = {
    "full_name": ['input[name="name"]'],
    "email": ['input[name="email"]'],
    "phone": ['input[name="phone"]'],
    "location": ['input[name="location"]'],
    "linkedin": ['input[name="urls[LinkedIn]"]'],
    "portfolio": ['input[name="urls[Portfolio]"]', 'input[name="urls[GitHub]"]'],
    "resume": ['input[name="resume"]', 'input[type="file"]'],
    "submit": ['button[type="submit"]', ".template-btn-submit"],
}


class LeverAdapter(Adapter):
    platform = "Lever"
    supports_prefill = True
    # Auto-apply is NOT enabled until the Lever submit pipeline is verified
    # (form detection → resume upload → required questions → confirmation →
    # application id → evidence), the same G0-G3 gates Greenhouse passed.
    # Until then Lever is manual-apply. Selectors below are scaffolding for that work.
    supports_auto_submit = False
    manual_only = True
    match_hosts = ("lever.co", "jobs.lever")
    match_sources = ("lever",)

    async def _live_submit(self, package, answers):
        return await autofill_and_submit(package, answers, SELECTORS)
