"""Minimal, deterministic currency conversion to USD using static rates.

Only currencies we are confident about are converted; anything else stays
unparsed rather than guessing (ADR-007: salary is optional enrichment).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_RATES_PATH = Path(__file__).resolve().parent.parent / "resources" / "fx_rates.json"


@lru_cache(maxsize=1)
def _rates() -> dict[str, float]:
    with open(_RATES_PATH, encoding="utf-8") as f:
        return json.load(f)


def to_usd(amount: float, currency: str) -> float | None:
    """Convert `amount` in `currency` to USD, or None if the currency is unknown."""
    rate = _rates().get(currency.upper())
    if rate is None:
        return None
    return round(amount * rate, 2)


def known_currencies() -> list[str]:
    return sorted(_rates().keys())
