"""Live-automation runtime guards.

LIVE_MODE is only meaningful if a Playwright browser is actually installed.
These helpers let callers fail loudly/clearly instead of crashing deep inside
Playwright. The Greenhouse inspector (G0-G1) is READ-ONLY and does not require
LIVE_MODE — it never submits and never writes to the DB.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def live_mode_enabled() -> bool:
    return os.getenv("JOBORA_LIVE", "0") == "1"


def _browsers_root() -> str:
    env = os.getenv("PLAYWRIGHT_BROWSERS_PATH")
    if env:
        return env
    home = os.path.expanduser("~")
    if sys.platform == "darwin":
        return os.path.join(home, "Library", "Caches", "ms-playwright")
    if sys.platform.startswith("win"):
        return os.path.join(home, "AppData", "Local", "ms-playwright")
    return os.path.join(home, ".cache", "ms-playwright")


def browser_available() -> bool:
    """True if a Chromium build is installed on disk.

    Pure filesystem check — does NOT launch Playwright, so it is safe to call
    from inside an async event loop (the sync API raises there).
    """
    base = Path(_browsers_root())
    if not base.exists():
        return False
    patterns = [
        "chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium",
        "chromium-*/chrome-linux/chrome",
        "chromium-*/chrome-win/chrome.exe",
        "chromium_headless_shell-*/chrome-*/headless_shell",
    ]
    return any(p.exists() for pat in patterns for p in base.glob(pat))


def live_ready() -> tuple[bool, str]:
    """Whether real submission could run, with a human-readable reason."""
    if not live_mode_enabled():
        return False, "JOBORA_LIVE is not set to 1 (submission disabled)."
    if not browser_available():
        return False, "Playwright Chromium is not installed (run: playwright install chromium)."
    return True, "live mode ready"
