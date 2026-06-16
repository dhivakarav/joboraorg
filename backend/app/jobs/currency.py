"""Salary normalisation to INR.

Parses free-text salary strings, detects the currency, and converts to Indian
Rupees using live exchange rates (free open.er-api.com endpoint) with an
in-memory TTL cache and a static fallback so it always works offline.
"""
from __future__ import annotations

import re
import time
from typing import Optional

import httpx

# Static fallback rates (units of currency per 1 INR is awkward; we store
# "INR per 1 unit of currency"). Updated periodically; live rates override.
_FALLBACK_INR_PER = {
    "INR": 1.0,
    "USD": 83.0,
    "EUR": 90.0,
    "GBP": 105.0,
    "AED": 22.6,
    "SGD": 62.0,
    "CAD": 61.0,
    "AUD": 55.0,
}

_RATE_CACHE: dict = {"ts": 0.0, "rates": {}}
_RATE_TTL = 6 * 3600  # refresh every 6 hours

CURRENCY_SYMBOLS = {
    "₹": "INR", "$": "USD", "€": "EUR", "£": "GBP", "د.إ": "AED",
}
CURRENCY_CODES = ["INR", "USD", "EUR", "GBP", "AED", "SGD", "CAD", "AUD", "RS", "RS.", "INR."]

_AMOUNT_RE = re.compile(r"(\d[\d,\.]*)\s*([kKmM])?")


async def _refresh_rates(client: httpx.AsyncClient) -> dict:
    """Return INR-per-unit-currency map, fetching live rates when stale."""
    now = time.time()
    if _RATE_CACHE["rates"] and now - _RATE_CACHE["ts"] < _RATE_TTL:
        return _RATE_CACHE["rates"]
    try:
        # base=INR gives "how many X per 1 INR"; we invert to get INR per X.
        r = await client.get("https://open.er-api.com/v6/latest/INR", timeout=8)
        r.raise_for_status()
        data = r.json()
        per_inr = data.get("rates", {})
        inr_per = {cur: (1.0 / v) for cur, v in per_inr.items() if v}
        inr_per["INR"] = 1.0
        if inr_per.get("USD"):
            _RATE_CACHE.update(ts=now, rates=inr_per)
            return inr_per
    except Exception:
        pass
    return _FALLBACK_INR_PER


def _detect_currency(text: str) -> Optional[str]:
    for sym, code in CURRENCY_SYMBOLS.items():
        if sym in text:
            return code
    up = text.upper()
    for code in ("INR", "USD", "EUR", "GBP", "AED", "SGD", "CAD", "AUD"):
        if re.search(r"\b" + code + r"\b", up):
            return code
    if re.search(r"\bRS\.?\b", up) or "RUPEE" in up:
        return "INR"
    return None


def _parse_amounts(text: str) -> list:
    vals = []
    for m in _AMOUNT_RE.finditer(text):
        num = m.group(1).replace(",", "")
        try:
            val = float(num)
        except ValueError:
            continue
        suffix = (m.group(2) or "").lower()
        if suffix == "k":
            val *= 1_000
        elif suffix == "m":
            val *= 1_000_000
        if val >= 100:  # ignore stray small numbers
            vals.append(val)
    return vals


def _fmt_inr(amount: float) -> str:
    """Indian-grouping formatted rupee string, abbreviated to L/Cr when large."""
    if amount >= 1e7:
        return f"₹{amount / 1e7:.2f} Cr"
    if amount >= 1e5:
        return f"₹{amount / 1e5:.2f} L"
    # Indian digit grouping (lakh/crore style) for plain values.
    s = f"{int(round(amount)):,}"
    return f"₹{s}"


async def salary_to_inr(salary_text: str, client: httpx.AsyncClient) -> str:
    """Convert a salary string to an INR display string. Empty if unparseable."""
    if not salary_text or not salary_text.strip():
        return ""
    currency = _detect_currency(salary_text)
    amounts = _parse_amounts(salary_text)
    if not amounts:
        return ""
    if currency is None:
        # No explicit currency — assume INR only if it already reads like rupees,
        # otherwise default to USD which is the most common on global boards.
        currency = "USD"
    rates = await _refresh_rates(client)
    rate = rates.get(currency, _FALLBACK_INR_PER.get(currency, 1.0))

    lo = min(amounts)
    hi = max(amounts)
    lo_inr = lo * rate
    hi_inr = hi * rate
    if currency == "INR":
        # Already INR; keep as-is.
        lo_inr, hi_inr = lo, hi
    if abs(hi_inr - lo_inr) < 1:
        return _fmt_inr(hi_inr) + ("/mo" if "month" in salary_text.lower() else "")
    return f"{_fmt_inr(lo_inr)} – {_fmt_inr(hi_inr)}"


def salary_to_inr_sync(salary_text: str) -> str:
    """Synchronous variant using fallback/cached rates only (no network)."""
    if not salary_text or not salary_text.strip():
        return ""
    currency = _detect_currency(salary_text) or "USD"
    amounts = _parse_amounts(salary_text)
    if not amounts:
        return ""
    rates = _RATE_CACHE["rates"] or _FALLBACK_INR_PER
    rate = rates.get(currency, _FALLBACK_INR_PER.get(currency, 1.0))
    lo, hi = min(amounts), max(amounts)
    if currency == "INR":
        lo_inr, hi_inr = lo, hi
    else:
        lo_inr, hi_inr = lo * rate, hi * rate
    if abs(hi_inr - lo_inr) < 1:
        return _fmt_inr(hi_inr)
    return f"{_fmt_inr(lo_inr)} – {_fmt_inr(hi_inr)}"
