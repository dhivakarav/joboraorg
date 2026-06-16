"""Real job-source providers."""
from .adzuna import AdzunaProvider
from .arbeitnow import ArbeitnowProvider
from .ashby import AshbyProvider
from .greenhouse import GreenhouseProvider
from .internshala import InternshalaProvider
from .jooble import JoobleProvider
from .jsearch import JSearchProvider
from .lever import LeverProvider
from .remotive import RemotiveProvider
from .wellfound import WellfoundProvider
from .workable import WorkableProvider

# Instantiated once; the aggregator filters by .available().
ALL_PROVIDERS = [
    RemotiveProvider(),
    ArbeitnowProvider(),
    GreenhouseProvider(),
    LeverProvider(),
    AshbyProvider(),          # official public posting API
    WorkableProvider(),       # discovery-only; needs an authorized account token
    AdzunaProvider(),
    JoobleProvider(),
    JSearchProvider(),        # Google-for-Jobs aggregator; needs a free RapidAPI key
    InternshalaProvider(),    # discovery-only; enabled when an authorized feed is set
    WellfoundProvider(),      # discovery-only; needs an authorized feed
]
