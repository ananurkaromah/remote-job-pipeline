"""Optional salary parsing (ADR-007): never a filter, NULL means unknown.

Keyword matching uses a word boundary and a look-back window so that
substrings like "rate" inside "Corporate" never trigger a false match.
"""
from __future__ import annotations

import re

from rjp.models import SalaryResult
from rjp.utils.fx import to_usd

_SALARY_KEYWORDS = re.compile(r"\b(salary|compensation|pay|rate|earn(?:s|ing|ings)?)\b", re.IGNORECASE)
_LOOKBACK_CHARS = 30

_CURRENCY_SYMBOLS = {"$": "USD", "\u20ac": "EUR", "\u00a3": "GBP", "rp": "IDR", "s$": "SGD"}
_CURRENCY_CODES = ("USD", "EUR", "GBP", "IDR", "SGD", "AUD", "CAD")

_PERIOD_RE = re.compile(r"\b(per\s*(year|month|hour|annum)|yearly|monthly|hourly|/\s*(yr|mo|hr))\b", re.I)

# Matches "$80,000 - $100,000", "80k-100k", "up to $5,000", "from $60,000", "$50/hr"
_RANGE_RE = re.compile(
    r"(?P<cur>\$|\u20ac|\u00a3|USD|EUR|GBP|IDR|SGD)?\s*"
    r"(?P<low>\d{1,3}(?:[,.]\d{3})*(?:\.\d+)?)\s*[kK]?"
    r"(?:\s*[-\u2013to]{1,3}\s*"
    r"(?P<cur2>\$|\u20ac|\u00a3|USD|EUR|GBP|IDR|SGD)?\s*"
    r"(?P<high>\d{1,3}(?:[,.]\d{3})*(?:\.\d+)?)\s*[kK]?)?"
)

_UP_TO_RE = re.compile(r"\bup to\b", re.I)
_FROM_RE = re.compile(r"\b(from|starting at|minimum)\b", re.I)


def _has_salary_context(text: str, match_start: int) -> bool:
    window = text[max(0, match_start - _LOOKBACK_CHARS):match_start]
    return bool(_SALARY_KEYWORDS.search(window)) or bool(_SALARY_KEYWORDS.search(
        text[match_start:match_start + 40]
    ))


def _parse_number(raw: str, has_k_suffix: bool) -> float:
    val = float(raw.replace(",", ""))
    return val * 1000 if has_k_suffix else val


def _detect_currency(cur_symbol: str | None, text_window: str) -> str:
    if cur_symbol:
        sym = cur_symbol.upper()
        if sym in _CURRENCY_CODES:
            return sym
        return _CURRENCY_SYMBOLS.get(cur_symbol.lower(), "USD")
    for code in _CURRENCY_CODES:
        if code in text_window:
            return code
    return "USD"


def _detect_period(text_window: str) -> str | None:
    m = _PERIOD_RE.search(text_window)
    if not m:
        return None
    token = (m.group(1) or "").lower()
    if "hour" in token or "hr" in token:
        return "hourly"
    if "month" in token or "mo" in token:
        return "monthly"
    return "yearly"


def parse_salary(text: str) -> SalaryResult:
    """Parse the first plausible salary mention in `text`. Conservative by design."""
    if not text:
        return SalaryResult(status="not_disclosed")

    for m in _RANGE_RE.finditer(text):
        if not m.group("low"):
            continue
        if not _has_salary_context(text, m.start()):
            continue

        window = text[max(0, m.start() - 20):m.end() + 20]
        has_k = "k" in m.group(0).lower()
        try:
            low = _parse_number(m.group("low"), has_k)
        except ValueError:
            continue
        high_raw = m.group("high")
        high = None
        if high_raw:
            try:
                high = _parse_number(high_raw, has_k)
            except ValueError:
                high = None

        currency = _detect_currency(m.group("cur") or m.group("cur2"), window)
        period = _detect_period(window)
        raw_snippet = window.strip()

        low_usd = to_usd(low, currency)
        high_usd = to_usd(high, currency) if high is not None else None

        if low_usd is None:
            return SalaryResult(status="unparsed", raw=raw_snippet, period=period)

        if high_usd is not None:
            return SalaryResult(
                status="disclosed", min_usd=min(low_usd, high_usd), max_usd=max(low_usd, high_usd),
                period=period, raw=raw_snippet,
            )

        # Single bound: figure out if it's a floor ("from $60k") or a ceiling ("up to $100k")
        if _UP_TO_RE.search(window):
            return SalaryResult(status="partial", max_usd=low_usd, period=period, raw=raw_snippet)
        if _FROM_RE.search(window):
            return SalaryResult(status="partial", min_usd=low_usd, period=period, raw=raw_snippet)
        return SalaryResult(status="partial", min_usd=low_usd, period=period, raw=raw_snippet)

    return SalaryResult(status="not_disclosed")
