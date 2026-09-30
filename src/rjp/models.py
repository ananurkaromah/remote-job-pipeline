"""Shared data structures used across extract, transform, and monitoring."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


def utcnow() -> datetime:
    return datetime.now(UTC)


class SourceStatus(str, Enum):
    OK = "ok"
    SKIPPED = "skipped"      # intentional: not scheduled, below quota reserve, already done today
    DEGRADED = "degraded"    # partial data kept after a PartialExtractionError
    FAILED = "failed"


@dataclass
class SourceResult:
    source: str
    status: SourceStatus
    jobs: list[dict] = field(default_factory=list)
    reason: str | None = None       # FailureReason value, if not OK
    detail: str = ""
    duration_s: float = 0.0

    @property
    def ok(self) -> bool:
        return self.status in (SourceStatus.OK, SourceStatus.DEGRADED, SourceStatus.SKIPPED)


@dataclass
class EligibilityResult:
    status: str            # "eligible" | "restricted" | "unknown"
    confidence: str        # "high" | "medium" | "low"
    evidence: list[str] = field(default_factory=list)
    reason: str = ""        # short machine-readable rule name, e.g. "worldwide_structured"
    timezone_hint: str | None = None


@dataclass
class RoleDecision:
    keep: bool
    role_match: str | None       # "core" | "adjacent" | None
    seniority: str                # "junior" | "mid" | "unknown" | "senior"
    min_years_required: int | None
    reason: str
    evidence: list[str] = field(default_factory=list)


@dataclass
class SalaryResult:
    status: str                   # "disclosed" | "partial" | "not_disclosed" | "unparsed"
    min_usd: float | None = None
    max_usd: float | None = None
    period: str | None = None     # "yearly" | "monthly" | "hourly"
    raw: str | None = None


@dataclass
class RunSummary:
    run_id: str
    started_at: datetime = field(default_factory=utcnow)
    source_results: list[SourceResult] = field(default_factory=list)
    dropped_counts: dict[str, int] = field(default_factory=dict)   # reason -> count
    duplicates_removed: int = 0
    transform_skipped: int = 0
    transform_total: int = 0
    loaded_count: int = 0
    eligibility_counts: dict[str, int] = field(default_factory=dict)

    @property
    def all_failed(self) -> bool:
        return len(self.source_results) > 0 and all(
            r.status == SourceStatus.FAILED for r in self.source_results
        )

    @property
    def any_degraded_or_failed(self) -> bool:
        return any(r.status in (SourceStatus.DEGRADED, SourceStatus.FAILED) for r in self.source_results)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "sources": {
                r.source: {"status": r.status.value, "count": len(r.jobs), "reason": r.reason}
                for r in self.source_results
            },
            "dropped_counts": self.dropped_counts,
            "duplicates_removed": self.duplicates_removed,
            "transform_skipped": self.transform_skipped,
            "transform_total": self.transform_total,
            "loaded_count": self.loaded_count,
            "eligibility_counts": self.eligibility_counts,
        }
