"""Orchestrator: guard clauses, exit codes (ADR-004).

Exit code 0: success or warning (including "0 jobs, verify this is
expected"). Exit code 1: only when every source failed, or the transform
failure ratio exceeds the configured threshold.
"""
from __future__ import annotations

import sys
import uuid
from datetime import date

from rjp import config
from rjp.extract.himalayas import HimalayasExtractor
from rjp.extract.jsearch import JSearchExtractor
from rjp.extract.registry import extract_all_sources
from rjp.extract.remoteok import RemoteOKExtractor
from rjp.extract.remotive import RemotiveExtractor
from rjp.load.r2 import get_today_envelope, load_raw_to_r2
from rjp.load.rejected import write_rejected
from rjp.load.supabase import apply_retention, delete_replaced, fetch_existing_window, load_to_supabase
from rjp.models import RunSummary, SourceStatus, utcnow
from rjp.monitoring.discord import notify_failure, notify_run_summary, notify_warning
from rjp.transform.dedup import deduplicate
from rjp.transform.pipeline import transform_all
from rjp.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


def build_extractors(run_envelope: dict | None) -> list:
    extractors = [RemoteOKExtractor(), RemotiveExtractor(), HimalayasExtractor()]
    extractors.append(JSearchExtractor(run_envelope=run_envelope))
    # Selenium sources (e.g. Glints) are intentionally excluded from the
    # default registry (ADR-022). Enable explicitly via
    # ENABLE_SELENIUM_SOURCES and add rjp.extract.experimental.glints here
    # if you have verified the portal's terms of service.
    return extractors


def run() -> int:
    setup_logging()
    run_id = uuid.uuid4().hex[:12]
    today = date.today()
    summary = RunSummary(run_id=run_id)

    logger.info("run_id=%s starting", run_id)

    run_envelope = get_today_envelope(today)
    extractors = build_extractors(run_envelope)
    results = extract_all_sources(extractors)
    summary.source_results = results

    failed = [r for r in results if r.status == SourceStatus.FAILED]
    if len(failed) == len(results):
        notify_failure("All sources failed. See logs for per-source reasons.", run_id)
        logger.error("run_id=%s all sources failed", run_id)
        return 1

    raw_jobs = [j for r in results for j in r.jobs]

    if not raw_jobs:
        notify_warning("0 jobs extracted from all healthy sources. Verify this is expected.", run_id)
        logger.warning("run_id=%s zero jobs extracted; no writes performed", run_id)
        return 0

    envelope_meta = {
        "run_id": run_id,
        "extracted_at": utcnow().isoformat(),
        "sources": {r.source: {"status": r.status.value, "count": len(r.jobs), "reason": r.reason} for r in results},
    }
    any_non_ok = any(r.status in (SourceStatus.DEGRADED, SourceStatus.FAILED) for r in results)
    load_raw_to_r2(raw_jobs, envelope_meta, run_date=today, partial=any_non_ok)

    kept, rejected_filter, skipped = transform_all(raw_jobs)
    summary.transform_total = len(raw_jobs)
    summary.transform_skipped = skipped

    if raw_jobs and (skipped / len(raw_jobs)) > config.TRANSFORM_FAILURE_THRESHOLD:
        notify_failure(
            f"Transform failure ratio {skipped}/{len(raw_jobs)} exceeds threshold "
            f"{config.TRANSFORM_FAILURE_THRESHOLD:.0%}. Likely a source format change.",
            run_id,
        )
        return 1

    for item in rejected_filter:
        summary.dropped_counts[item["reason"]] = summary.dropped_counts.get(item["reason"], 0) + 1

    if not kept:
        write_rejected(rejected_filter, run_id, today)
        notify_warning("0 jobs left after filtering. Verify this is expected.", run_id)
        logger.warning("run_id=%s zero jobs survived filtering", run_id)
        return 0

    # Dedup against the new batch AND existing rows in the retention window (ADR-011)
    try:
        existing = fetch_existing_window()
    except Exception:
        logger.exception("could not fetch existing window for dedup; deduping new batch only")
        existing = []

    winners, losers = deduplicate(kept + existing)
    new_winner_ids = {w["job_id"] for w in winners} & {k["job_id"] for k in kept}
    winners_to_upsert = [w for w in winners if w["job_id"] in new_winner_ids or w not in existing]
    summary.duplicates_removed = len(losers)

    replaced_ids = [
        e["job_id"] for e in existing
        if e["job_id"] not in {w["job_id"] for w in winners} and e["job_id"] not in {loser["job_id"] for loser in losers}
    ]

    rejected_dedup = [{"title": loser.get("title"), "reason": "duplicate", "duplicate_of": loser.get("duplicate_of")} for loser in losers]
    write_rejected(rejected_filter + rejected_dedup, run_id, today)

    from rjp.embed.encoder import encode_documents
    from rjp.embed.templates import build_embedding_text

    new_jobs = [w for w in winners_to_upsert if w.get("job_id") in {k["job_id"] for k in kept}]
    if new_jobs:
        texts = [build_embedding_text(j) for j in new_jobs]
        embeddings = encode_documents(texts)
        for job, text, emb in zip(new_jobs, texts, embeddings, strict=True):
            job["embedding_text"] = text
            job["embedding"] = emb

        if replaced_ids:
            delete_replaced(replaced_ids)
        load_to_supabase(new_jobs)
        summary.loaded_count = len(new_jobs)
        for job in new_jobs:
            status = job.get("eligibility_status", "unknown")
            summary.eligibility_counts[status] = summary.eligibility_counts.get(status, 0) + 1
    else:
        summary.loaded_count = 0

    try:
        apply_retention()
    except Exception:
        logger.exception("retention cleanup failed; continuing (non-fatal)")

    notify_run_summary(summary)
    logger.info("run_id=%s done: loaded=%d duplicates_removed=%d", run_id, summary.loaded_count, summary.duplicates_removed)
    return 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
