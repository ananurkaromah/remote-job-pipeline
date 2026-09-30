"""Role family and seniority classification (ADR-008, ADR-009).

Two independent decisions:
  1. Role family: core / adjacent / excluded (is this a Data Engineering role?)
  2. Seniority: junior / mid / unknown / senior, with a strict cutoff at
     MAX_YEARS_REQUIRED_EXCLUSIVE (default 3): any stated requirement of 3+
     years drops the posting. No "stretch" tier (ADR-009, decided 2026-09-28).

Both functions are pure and side-effect free so they can be unit tested
directly against fixture titles and descriptions.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml

from rjp import config
from rjp.models import RoleDecision

_RESOURCES = Path(__file__).resolve().parent.parent / "resources"

_WORD_NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

# "2-3 years", "3+ years", "at least 3 years", "three years", etc.
_YEARS_RE = re.compile(
    r"(?P<low>\d{1,2}|" + "|".join(_WORD_NUMBERS) + r")"
    r"(?:\s*[-\u2013]\s*(?P<high>\d{1,2}))?"
    r"\s*\+?\s*"
    r"years?",
    re.IGNORECASE,
)

_CEILING_MARKERS = ("up to", "less than", "no more than", "fewer than")
_SOFT_MARKERS = ("preferred", "nice to have", "a plus", "bonus", "ideally")


@lru_cache(maxsize=1)
def _patterns() -> dict:
    with open(_RESOURCES / "role_patterns.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _word_to_num(token: str) -> int:
    token = token.lower()
    return _WORD_NUMBERS.get(token, None) if token in _WORD_NUMBERS else int(token)


def classify_role(title: str, description: str = "") -> tuple[str | None, list[str]]:
    """Return (role_match, evidence). role_match is 'core', 'adjacent', or None (excluded)."""
    from rjp.transform.normalization import normalize_title

    t = normalize_title(title)
    patterns = _patterns()

    for phrase in patterns["excluded_titles"]:
        if phrase in t:
            return None, [f"excluded_title:{phrase}"]
    for phrase in patterns["core_titles"]:
        if phrase in t:
            return "core", [f"core_title:{phrase}"]
    for phrase in patterns["adjacent_titles"]:
        if phrase in t:
            return "adjacent", [f"adjacent_title:{phrase}"]

    return None, ["no_role_match"]


def _extract_years_lower_bounds(text: str) -> list[tuple[int, str]]:
    """Find every 'N years' style mention that reads as a MINIMUM requirement.

    Ceiling phrases ("up to 3 years") and soft/preferred mentions are
    excluded from the requirement calculation but kept as evidence text.
    """
    bounds: list[tuple[int, str]] = []
    lower_text = text.lower()
    for m in _YEARS_RE.finditer(lower_text):
        start = m.start()
        window = lower_text[max(0, start - 20):start]
        snippet = lower_text[max(0, start - 25):m.end() + 5].strip()

        if any(marker in window for marker in _CEILING_MARKERS):
            continue  # a ceiling, not a minimum requirement
        if any(marker in lower_text[m.end():m.end() + 15] for marker in _SOFT_MARKERS):
            continue  # "1+ years, 3+ preferred" -> preferred is not required

        low_raw = m.group("low")
        try:
            low = _word_to_num(low_raw)
        except (ValueError, TypeError):
            continue
        if low is None:
            continue
        bounds.append((low, snippet))
    return bounds


def classify_seniority(title: str, description: str = "") -> RoleDecision:
    """Decide junior/mid/unknown/senior and whether the posting should be kept.

    Rules (ADR-009):
      1. Senior keywords in the TITLE only -> drop.
      2. Junior keywords in the TITLE -> keep, seniority=junior.
      3. Otherwise, look at years required in the description. The largest
         lower bound found is treated as the requirement. >= 3 -> drop.
         Ceilings ("up to 3 years") and "preferred" mentions are ignored.
      4. No years mentioned at all -> keep, seniority=unknown.
    """
    from rjp.transform.normalization import normalize_title

    t = normalize_title(title)
    patterns = _patterns()
    evidence: list[str] = []

    for kw in patterns["senior_title_keywords"]:
        if kw.strip() in t:
            return RoleDecision(
                keep=False, role_match=None, seniority="senior",
                min_years_required=None, reason="dropped:senior_title",
                evidence=[f"title_keyword:{kw.strip()}"],
            )

    for kw in patterns["junior_title_keywords"]:
        if kw.strip() in t:
            return RoleDecision(
                keep=True, role_match=None, seniority="junior",
                min_years_required=None, reason="kept:junior_title",
                evidence=[f"title_keyword:{kw.strip()}"],
            )

    bounds = _extract_years_lower_bounds(description or "")
    if not bounds:
        return RoleDecision(
            keep=True, role_match=None, seniority="unknown",
            min_years_required=None, reason="kept:no_years_mentioned",
            evidence=[],
        )

    max_lower_bound = max(b[0] for b in bounds)
    evidence = [snippet for _, snippet in bounds]

    if max_lower_bound >= config.MAX_YEARS_REQUIRED_EXCLUSIVE:
        return RoleDecision(
            keep=False, role_match=None, seniority="senior",
            min_years_required=max_lower_bound, reason="dropped:years_ge_cutoff",
            evidence=evidence,
        )

    return RoleDecision(
        keep=True, role_match=None,
        seniority="junior" if max_lower_bound <= 1 else "mid",
        min_years_required=max_lower_bound, reason="kept:years_below_cutoff",
        evidence=evidence,
    )


def classify(title: str, description: str = "") -> RoleDecision:
    """Combine role-family and seniority into one decision."""
    role_match, role_evidence = classify_role(title, description)
    if role_match is None:
        return RoleDecision(
            keep=False, role_match=None, seniority="unknown",
            min_years_required=None, reason="dropped:not_data_engineering_role",
            evidence=role_evidence,
        )

    seniority_decision = classify_seniority(title, description)
    if not seniority_decision.keep:
        return seniority_decision

    seniority_decision.role_match = role_match
    seniority_decision.evidence = role_evidence + seniority_decision.evidence
    return seniority_decision
