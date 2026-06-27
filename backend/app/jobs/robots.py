"""robots.txt compliance checker.

Used to gate any HTML-scraping provider: before fetching a path we confirm the
site's robots.txt actually allows it for our user-agent. Official JSON APIs
(Greenhouse, Lever, Adzuna, …) are exempt because they are published,
documented endpoints intended for programmatic access — but we still expose
this so scraping providers can be added safely and lawfully.

WHY NOT urllib.robotparser:
Python's stdlib ``urllib.robotparser`` silently FAILS OPEN on real-world
robots files that lead with wildcard ``Disallow`` lines (e.g. Internshala's
``Disallow: /*,*`` / ``Disallow: /*?*``): it then returns ``allowed=True`` for
paths that are explicitly disallowed further down (``/internship/search/``,
``/api/`` …). That turns a safety gate into a no-op. This module implements a
small, wildcard-aware matcher (Google's ``*`` / ``$`` semantics, longest-match-
wins, Allow beats Disallow on ties) and FAILS CLOSED on any fetch/parse error.
"""
from __future__ import annotations

import re
import time
import urllib.request
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

USER_AGENT = "JoboraBot/1.0 (+https://jobora.app/bot; job-aggregator)"
# The product token we present to robots.txt (group matching is case-insensitive).
_AGENT_TOKEN = "joborabot"

# Cache parsed rule groups per origin for an hour to avoid hammering sites.
# Value: (timestamp, groups | None). None means "could not fetch" → fail closed.
_CACHE: Dict[str, Tuple[float, Optional[Dict[str, List[Tuple[str, str]]]]]] = {}
_TTL = 3600.0


def _fetch_robots(base: str) -> Optional[str]:
    """Fetch robots.txt text. Returns None on any error (→ fail closed)."""
    try:
        req = urllib.request.Request(f"{base}/robots.txt", headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=8) as resp:  # nosec B310 — URL is https://host/robots.txt, not user-supplied
            if resp.status != 200:
                return None
            return resp.read().decode("utf-8", "replace")
    except Exception:
        return None


def _parse(text: str) -> Dict[str, List[Tuple[str, str]]]:
    """Parse robots.txt into {agent_token_lower: [(rule_type, pattern), ...]}.

    ``rule_type`` is "allow" or "disallow". Consecutive ``User-agent`` lines share
    the rule block that follows them (standard robots grouping).
    """
    groups: Dict[str, List[Tuple[str, str]]] = {}
    current_agents: List[str] = []
    expecting_rules = False  # have we seen a rule since the last UA line?
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field = field.strip().lower()
        value = value.strip()
        if field == "user-agent":
            if expecting_rules:
                # New group starts; reset the agent accumulator.
                current_agents = []
                expecting_rules = False
            agent = value.lower()
            current_agents.append(agent)
            groups.setdefault(agent, [])
        elif field in ("allow", "disallow"):
            expecting_rules = True
            for agent in current_agents or ["*"]:
                groups.setdefault(agent, []).append((field, value))
    return groups


def _select_group(groups: Dict[str, List[Tuple[str, str]]], agent_token: str
                  ) -> List[Tuple[str, str]]:
    """Pick the most specific matching UA group; else the ``*`` group; else []."""
    best: Optional[str] = None
    for ua in groups:
        if ua == "*":
            continue
        # robots group matches if our token starts with / contains the UA token.
        if ua and (agent_token.startswith(ua) or ua in agent_token):
            if best is None or len(ua) > len(best):
                best = ua
    if best is not None:
        return groups[best]
    return groups.get("*", [])


def _pattern_to_regex(pattern: str) -> re.Pattern:
    """Convert a robots path pattern (with * and trailing $) to a regex."""
    anchored_end = pattern.endswith("$")
    if anchored_end:
        pattern = pattern[:-1]
    out = []
    for ch in pattern:
        if ch == "*":
            out.append(".*")
        else:
            out.append(re.escape(ch))
    regex = "^" + "".join(out) + ("$" if anchored_end else "")
    return re.compile(regex)


def _allowed_by_group(rules: List[Tuple[str, str]], path: str) -> bool:
    """Google-style evaluation: longest matching pattern wins; Allow beats
    Disallow on equal length. Empty Disallow = allow all. Default = allow."""
    best_len = -1
    best_type = "allow"  # default allow when nothing matches
    for rule_type, pattern in rules:
        if pattern == "" and rule_type == "disallow":
            # "Disallow:" with empty value explicitly allows everything → ignore.
            continue
        try:
            if _pattern_to_regex(pattern).match(path):
                plen = len(pattern.rstrip("$"))
                if plen > best_len or (plen == best_len and rule_type == "allow"):
                    best_len = plen
                    best_type = rule_type
        except re.error:
            continue
    return best_type == "allow"


def _get_groups(base: str) -> Optional[Dict[str, List[Tuple[str, str]]]]:
    now = time.time()
    cached = _CACHE.get(base)
    if cached and now - cached[0] < _TTL:
        return cached[1]
    text = _fetch_robots(base)
    groups = _parse(text) if text is not None else None
    _CACHE[base] = (now, groups)
    return groups


def can_fetch(url: str, agent: str = _AGENT_TOKEN) -> bool:
    """Return True only if robots.txt allows our agent to fetch ``url``.

    Fails CLOSED: if robots.txt can't be fetched/parsed, returns False.
    """
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return False
    base = f"{parsed.scheme}://{parsed.netloc}"
    groups = _get_groups(base)
    if groups is None:
        return False  # fail closed
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    rules = _select_group(groups, agent.lower())
    if not rules:
        return True  # no applicable rules → allowed (standard robots semantics)
    return _allowed_by_group(rules, path)


def clear_cache() -> None:
    _CACHE.clear()
