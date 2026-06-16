"""Generic fallback adapter for company career pages / unknown ATS.

We can't safely automate an arbitrary career site, so this is manual-only. It
still prepares the profile package so the user has everything ready to paste.
"""
from __future__ import annotations

from .base import Adapter


class GenericAdapter(Adapter):
    platform = "Company Career Page"
    supports_prefill = True
    supports_auto_submit = False
    manual_only = True

    def matches(self, job: dict) -> bool:
        # Catch-all; the registry only falls back to this last.
        return True
