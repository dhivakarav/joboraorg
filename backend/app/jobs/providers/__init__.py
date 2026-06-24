"""Real job-source providers."""
from .adzuna import AdzunaProvider
from .arbeitnow import ArbeitnowProvider
from .ashby import AshbyProvider
from .greenhouse import GreenhouseProvider
from .internshala import InternshalaProvider
from .jooble import JoobleProvider
from .jobicy import JobicyProvider
from .jsearch import JSearchProvider
from .lever import LeverProvider
from .remoteok import RemoteOKProvider
from .remotive import RemotiveProvider
from .smartrecruiters import SmartRecruitersProvider
from .themuse import TheMuseProvider
from .wellfound import WellfoundProvider
from .workable import WorkableProvider

# Instantiated once; the aggregator filters by .available().
ALL_PROVIDERS = [
    RemotiveProvider(),
    ArbeitnowProvider(),
    GreenhouseProvider(),
    LeverProvider(),
    AshbyProvider(),          # official public posting API
    SmartRecruitersProvider(),  # official public API; India-hiring boards (Freshworks…)
    TheMuseProvider(),        # official public API; India + global, no key
    RemoteOKProvider(),       # official public API; global remote, no key
    JobicyProvider(),         # official public API; global remote, no key
    WorkableProvider(),       # discovery-only; needs an authorized account token
    AdzunaProvider(),
    JoobleProvider(),
    JSearchProvider(),        # Google-for-Jobs aggregator; needs a free RapidAPI key
    InternshalaProvider(),    # discovery-only; enabled when an authorized feed is set
    WellfoundProvider(),      # discovery-only; needs an authorized feed
]
