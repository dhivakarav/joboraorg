"""Ashby adapter — prefill + (opt-in) auto-submit."""
from __future__ import annotations

from .base import Adapter
from .playwright_fill import autofill_and_submit

SELECTORS = {
    "full_name": ['input[name="_systemfield_name"]', 'input[aria-label*="Name"]'],
    "email": ['input[name="_systemfield_email"]', 'input[type="email"]'],
    "phone": ['input[name="_systemfield_phone"]', 'input[type="tel"]'],
    "location": ['input[aria-label*="Location"]'],
    "linkedin": ['input[aria-label*="LinkedIn"]'],
    "portfolio": ['input[aria-label*="Website"]', 'input[aria-label*="Portfolio"]'],
    "resume": ['input[type="file"]'],
    "submit": ['button[type="submit"]', 'button:has-text("Submit Application")'],
}


class AshbyAdapter(Adapter):
    platform = "Ashby"
    supports_prefill = True
    # Manual until the Ashby submit pipeline is verified (G0-G3). Scaffolding below.
    supports_auto_submit = False
    manual_only = True
    match_hosts = ("ashbyhq.com", "jobs.ashby")
    match_sources = ("ashby",)

    async def _live_submit(self, package, answers):
        return await autofill_and_submit(package, answers, SELECTORS)
