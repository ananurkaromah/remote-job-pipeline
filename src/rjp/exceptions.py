"""Extractor error contract (see docs/decisions.md ADR-003, ADR-021).

Extractors never swallow errors and return an empty list to signal failure.
An empty list means "the source is healthy and has no matching data". Any
failure is raised, so it is always attributed to a named source and reason.
"""
from __future__ import annotations

from enum import Enum


class FailureReason(str, Enum):
    NETWORK = "network"          # timeout, DNS, connection reset
    HTTP_STATUS = "http_status"  # unexpected 4xx/5xx after retries
    AUTH = "auth"                # 401/403, bad API key
    QUOTA = "quota"              # 429 / monthly quota exhausted
    PARSE = "parse"              # response shape changed, required keys missing
    BLOCKED = "blocked"          # captcha / anti-bot page
    DISABLED = "disabled"        # source intentionally disabled (e.g. Selenium)


class ExtractionError(Exception):
    """Raised by an extractor when it cannot produce a usable result at all."""

    def __init__(self, source: str, reason: FailureReason, detail: str = ""):
        self.source = source
        self.reason = reason
        self.detail = detail
        super().__init__(f"[{source}] {reason.value}: {detail}")


class PartialExtractionError(ExtractionError):
    """Raised when an extractor collected some jobs before failing.

    The registry keeps ``jobs`` and marks the source ``degraded`` instead of
    ``failed`` (ADR-021). Used mainly by quota-limited sources such as
    JSearch, where the first query succeeds and a later one hits HTTP 429.
    """

    def __init__(self, source: str, reason: FailureReason, jobs: list, detail: str = ""):
        super().__init__(source, reason, detail)
        self.jobs = jobs
