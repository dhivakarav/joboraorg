"""Greenhouse adapter — prefill + (opt-in) auto-submit."""
from __future__ import annotations

from .base import Adapter
from .playwright_fill import autofill_and_submit

SELECTORS = {
    "full_name": ['input[name="job_application[first_name]"]', "#first_name", 'input[autocomplete="name"]'],
    "email": ['input[name="job_application[email]"]', "#email"],
    "phone": ['input[name="job_application[phone]"]', "#phone"],
    "location": ['input[name="job_application[location]"]', "#auto_complete_input"],
    "linkedin": ['input[name*="linkedin"]'],
    "portfolio": ['input[name*="website"]', 'input[name*="portfolio"]'],
    "resume": ['input[type="file"]'],
    "submit": ['#submit_app', 'button[type="submit"]'],
}


class GreenhouseAdapter(Adapter):
    platform = "Greenhouse"
    supports_prefill = True
    supports_auto_submit = True
    manual_only = False
    match_hosts = ("greenhouse.io", "boards.greenhouse", "job-boards.greenhouse")
    match_sources = ("greenhouse",)

    async def _live_submit(self, package, answers):
        return await autofill_and_submit(package, answers, SELECTORS)
