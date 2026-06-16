"""Workable adapter — prefill + (opt-in) auto-submit."""
from __future__ import annotations

from .base import Adapter
from .playwright_fill import autofill_and_submit

SELECTORS = {
    "full_name": ['input[name="firstname"]', 'input[aria-label*="name"]'],
    "email": ['input[name="email"]', 'input[type="email"]'],
    "phone": ['input[name="phone"]', 'input[type="tel"]'],
    "location": ['input[name="address"]'],
    "linkedin": ['input[name*="LINKEDIN"]', 'input[aria-label*="LinkedIn"]'],
    "portfolio": ['input[aria-label*="Website"]'],
    "resume": ['input[type="file"]'],
    "submit": ['button[type="submit"]', 'button:has-text("Submit")'],
}


class WorkableAdapter(Adapter):
    platform = "Workable"
    supports_prefill = True
    # Manual until the Workable submit pipeline is verified (G0-G3). Scaffolding below.
    supports_auto_submit = False
    manual_only = True
    match_hosts = ("workable.com", "apply.workable")
    match_sources = ("workable",)

    async def _live_submit(self, package, answers):
        return await autofill_and_submit(package, answers, SELECTORS)
