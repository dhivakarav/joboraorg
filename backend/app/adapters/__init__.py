"""Adapter registry.

Selection is ordered: specific platforms first, the generic career-page adapter
last as a catch-all. Adding a platform is a one-line registration here, which is
what makes the apply layer scale to new integrations.
"""
from typing import List

from .ashby import AshbyAdapter
from .base import Adapter
from .generic import GenericAdapter
from .greenhouse import GreenhouseAdapter
from .internshala import InternshalaAdapter
from .lever import LeverAdapter
from .linkedin import LinkedInAdapter
from .wellfound import WellfoundAdapter
from .workable import WorkableAdapter
from .workday import WorkdayAdapter

# Order matters: most specific → generic fallback.
_REGISTRY: List[Adapter] = [
    GreenhouseAdapter(),
    LeverAdapter(),
    AshbyAdapter(),
    WorkableAdapter(),
    WorkdayAdapter(),
    LinkedInAdapter(),
    InternshalaAdapter(),   # manual-only (discovery only in Phase 1)
    WellfoundAdapter(),     # manual-only (discovery only; authorized feed pending)
    GenericAdapter(),  # catch-all, keep last
]


def adapter_for(job: dict) -> Adapter:
    for adapter in _REGISTRY:
        if adapter.matches(job):
            return adapter
    return _REGISTRY[-1]


def platform_capabilities() -> list:
    out = []
    for a in _REGISTRY:
        out.append({
            "platform": a.platform,
            "auto_submit": a.supports_auto_submit,
            "prefill": a.supports_prefill,
            "manual_only": a.manual_only,
        })
    return out
