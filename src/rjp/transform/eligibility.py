"""Indonesia eligibility classification: eligible / restricted / unknown (ADR-005, ADR-006).

Evidence is evaluated from the most to the least reliable source:
  1. Structured API fields (candidate_required_location, country lists, etc.)
  2. Title and tags
  3. Description text (regex over positive/negative phrase lists)

Ambiguity resolves toward keeping data: conflicting or absent signals
produce 'unknown', never a drop. Only an explicit, unambiguous restriction
produces 'restricted'. Timezone overlap requirements are recorded separately
and never change the status (ADR-005).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from rjp.models import EligibilityResult

_RESOURCES = Path(__file__).resolve().parent.parent / "resources"


@lru_cache(maxsize=1)
def _patterns() -> dict:
    with open(_RESOURCES / "eligibility_patterns.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=1)
def _countries() -> list[str]:
    with open(_RESOURCES / "countries.txt", encoding="utf-8") as f:
        return [line.strip().lower() for line in f if line.strip() and not line.startswith("#")]


def _find_phrase(text: str, phrase: str) -> bool:
    return phrase in text


def _has_negation_guard(text: str, match_start: int, guards: list[str]) -> bool:
    window = text[max(0, match_start - 40):match_start]
    return any(g in window for g in guards)


def classify_from_structured_location(location_field: str | None) -> EligibilityResult | None:
    """Rule #1-3: a structured API location field is the most reliable signal."""
    if not location_field:
        return None
    loc = location_field.lower()

    if any(p in loc for p in ("worldwide", "anywhere", "global", "apac", "asia", "indonesia")):
        return EligibilityResult(
            status="eligible", confidence="high",
            evidence=[location_field], reason="structured_worldwide_or_apac",
        )

    # Country list present but Indonesia is not in it (rule #3)
    mentioned = [c for c in _countries() if c in loc and c not in ("worldwide", "anywhere", "global")]
    if mentioned and "indonesia" not in mentioned:
        # Only treat as restricted if it reads like an explicit allow-list
        # (comma/slash separated country names), not a single incidental word.
        if len(mentioned) >= 1 and any(sep in loc for sep in (",", "/", " and ", " or ")):
            return EligibilityResult(
                status="restricted", confidence="high",
                evidence=[location_field], reason="structured_country_list_excludes_id",
            )
    return None


def classify_from_text(text: str) -> EligibilityResult:
    """Rule #4-7: regex over description/title text. Lower confidence than structured fields."""
    if not text:
        return EligibilityResult(status="unknown", confidence="low", reason="no_info")

    lower = text.lower()
    patterns = _patterns()

    positive_hits = []
    for phrase in patterns["positive_phrases"]:
        idx = lower.find(phrase)
        if idx != -1 and not _has_negation_guard(lower, idx, patterns["negation_guards"]):
            positive_hits.append(phrase)

    negative_hits = []
    for phrase in patterns["negative_phrases"]:
        idx = lower.find(phrase)
        if idx != -1 and not _has_negation_guard(lower, idx, patterns["negation_guards"]):
            negative_hits.append(phrase)

    timezone_hits = [p for p in patterns["timezone_phrases"] if p in lower]
    timezone_hint = ", ".join(timezone_hits[:3]) if timezone_hits else None

    if positive_hits and negative_hits:
        return EligibilityResult(
            status="unknown", confidence="low",
            evidence=positive_hits + negative_hits, reason="conflict",
            timezone_hint=timezone_hint,
        )
    if positive_hits:
        return EligibilityResult(
            status="eligible", confidence="medium",
            evidence=positive_hits, reason="description_worldwide_or_apac",
            timezone_hint=timezone_hint,
        )
    if negative_hits:
        return EligibilityResult(
            status="restricted", confidence="medium",
            evidence=negative_hits, reason="description_hard_restriction",
            timezone_hint=timezone_hint,
        )

    soft_hits = [p for p in patterns["soft_negative_phrases"] if p in lower]
    if soft_hits:
        return EligibilityResult(
            status="unknown", confidence="low",
            evidence=soft_hits, reason="soft_visa_signal_only",
            timezone_hint=timezone_hint,
        )

    return EligibilityResult(status="unknown", confidence="low", reason="no_info", timezone_hint=timezone_hint)


def classify_eligibility(
    title: str = "",
    description: str = "",
    structured_location: str | None = None,
) -> EligibilityResult:
    """Full eligibility decision combining structured fields, title, and description."""
    structured = classify_from_structured_location(structured_location)
    if structured is not None:
        return structured

    title_result = classify_from_text(title)
    if title_result.status != "unknown":
        # Title-level signal is more reliable than the (usually longer, noisier) description.
        title_result.confidence = "high" if title_result.confidence == "medium" else title_result.confidence
        return title_result

    return classify_from_text(description)
