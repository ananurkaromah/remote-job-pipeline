"""Builds Discord message text and embed color from a RunSummary (ADR-004, ADR-017)."""
from __future__ import annotations

from rjp.models import RunSummary, SourceStatus

COLOR_SUCCESS = 0x2ECC71  # green
COLOR_WARNING = 0xF1C40F  # yellow
COLOR_FAILURE = 0xE74C3C  # red


def classify_summary(summary: RunSummary) -> tuple[str, int]:
    """Return (level, color) where level is 'success' | 'warning' | 'failure'."""
    if summary.all_failed:
        return "failure", COLOR_FAILURE
    if summary.any_degraded_or_failed or summary.loaded_count == 0:
        return "warning", COLOR_WARNING
    return "success", COLOR_SUCCESS


def format_summary(summary: RunSummary) -> tuple[str, int]:
    level, color = classify_summary(summary)

    lines = [f"**remote-job-pipeline** | run `{summary.run_id}`"]

    if level == "failure":
        details = ", ".join(f"{r.source}={r.reason}" for r in summary.source_results)
        lines.append(f"All sources failed: {details}")
        return "\n".join(lines), color

    source_counts = ", ".join(f"{r.source} {len(r.jobs)}" for r in summary.source_results if r.status != SourceStatus.SKIPPED)
    total_extracted = sum(len(r.jobs) for r in summary.source_results)
    lines.append(f"extracted {total_extracted} ({source_counts})")

    for r in summary.source_results:
        if r.status == SourceStatus.DEGRADED:
            lines.append(f"⚠ {r.source} DEGRADED: {r.reason} ({r.detail})")
        elif r.status == SourceStatus.FAILED:
            lines.append(f"⚠ {r.source} FAILED: {r.reason} ({r.detail})")
        elif r.status == SourceStatus.SKIPPED:
            lines.append(f"ℹ {r.source} skipped: {r.detail}")

    if summary.dropped_counts:
        dropped = ", ".join(f"{v} {k}" for k, v in summary.dropped_counts.items())
        lines.append(f"dropped: {dropped}")
    if summary.duplicates_removed:
        lines.append(f"duplicates removed: {summary.duplicates_removed}")

    if total_extracted > 0 and summary.loaded_count == 0:
        lines.append("loaded 0 jobs. **Verify this is expected.**")
    elif total_extracted == 0:
        lines.append("0 jobs extracted from all healthy sources. **Verify this is expected.**")
    else:
        elig = ", ".join(f"{k} {v}" for k, v in summary.eligibility_counts.items())
        lines.append(f"loaded {summary.loaded_count} ({elig})")

    if summary.transform_skipped:
        lines.append(f"({summary.transform_skipped}/{summary.transform_total} skipped due to transform errors)")

    return "\n".join(lines), color
