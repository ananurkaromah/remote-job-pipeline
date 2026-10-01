"""Quota budgeting for rate-limited sources such as JSearch (ADR-021).

A source can end a run as SKIPPED (intentional, no request made), DEGRADED
(some requests succeeded before quota ran out), or FAILED (no usable data).
The registry (extract/registry.py) interprets QuotaSkip / the extractor's
own PartialExtractionError to set the final SourceStatus.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from rjp import config


class QuotaSkip(Exception):
    """Raised by an extractor's own budget check to signal an intentional skip."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


@dataclass
class RunBudget:
    """Tracks how many requests a quota-limited source may make this run."""

    max_requests_per_run: int
    run_days: list[str]           # e.g. ["MON", "THU"]
    quota_reserve: int
    remaining_quota: int | None = None   # from provider headers, if known

    _used: int = 0

    def check_scheduled_today(self, now: datetime | None = None) -> None:
        now = now or datetime.now(timezone.utc)
        today = now.strftime("%a").upper()
        if self.run_days and today not in self.run_days:
            raise QuotaSkip(f"not scheduled today ({today} not in {self.run_days})")

    def check_reserve(self) -> None:
        if self.remaining_quota is not None and self.remaining_quota <= self.quota_reserve:
            raise QuotaSkip(
                f"remaining quota ({self.remaining_quota}) at or below reserve ({self.quota_reserve})"
            )

    def can_make_request(self) -> bool:
        if self._used >= self.max_requests_per_run:
            return False
        if self.remaining_quota is not None and self.remaining_quota - self._used <= self.quota_reserve:
            return False
        return True

    def record_request(self) -> None:
        self._used += 1

    @classmethod
    def from_config(cls) -> RunBudget:
        return cls(
            max_requests_per_run=config.JSEARCH_MAX_REQUESTS_PER_RUN,
            run_days=config.JSEARCH_RUN_DAYS,
            quota_reserve=config.JSEARCH_QUOTA_RESERVE,
        )


def already_extracted_today(source: str, run_envelope: dict | None) -> bool:
    """True if today's raw-lake envelope already has a healthy result for `source`.

    Lets a manual re-run on the same day skip a quota-limited source instead
    of burning quota again.
    """
    if not run_envelope:
        return False
    sources = run_envelope.get("sources", {})
    entry = sources.get(source)
    return bool(entry and entry.get("status") == "ok" and entry.get("count", 0) > 0)