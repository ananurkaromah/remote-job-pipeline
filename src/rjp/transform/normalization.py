"""Normalization helpers used by dedup and downstream filters."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_RESOURCES = Path(__file__).resolve().parent.parent / "resources"

_TRACKING_PARAMS_PREFIXES = ("utm_", "ref", "source", "gh_src", "gh_jid")


@lru_cache(maxsize=1)
def _company_suffixes() -> set[str]:
    with open(_RESOURCES / "company_suffixes.txt", encoding="utf-8") as f:
        return {line.strip().lower() for line in f if line.strip() and not line.startswith("#")}


def normalize_title(title: str) -> str:
    """Lowercase, strip punctuation and remote/location annotations, expand abbreviations."""
    if not title:
        return ""
    t = title.lower()
    t = re.sub(r"\(remote[^)]*\)", "", t)
    t = re.sub(r"\bsr\.?\b", "senior", t)
    t = re.sub(r"\bjr\.?\b", "junior", t)
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def normalize_company(company: str) -> str:
    """Lowercase, strip punctuation and common suffixes (Inc, LLC, PT, Tbk, ...)."""
    if not company:
        return ""
    c = company.lower()
    c = re.sub(r"[^\w\s]", " ", c)
    tokens = [tok for tok in c.split() if tok not in _company_suffixes()]
    return " ".join(tokens).strip()


def canonical_url(url: str) -> str:
    """Strip tracking params, fragment, and trailing slash for duplicate detection."""
    if not url:
        return ""
    parts = urlsplit(url)
    query = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not any(k.lower().startswith(p) for p in _TRACKING_PARAMS_PREFIXES)
    ]
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))
