"""Idempotent upsert into Supabase PostgreSQL (ADR-014, ADR-015).

Connects with the `pipeline_writer` role (or the admin credential during the
MVP phase -- see docs/deployment.md "Database roles"). Never the
`agent_readonly` credential, which is read-only by design.
"""
from __future__ import annotations

import json
from typing import Any

from rjp import config
from rjp.utils.logging import get_logger

logger = get_logger(__name__)

_COLUMNS = [
    "job_id", "source", "origin_portal", "external_id", "url", "is_direct_apply_url",
    "title", "company", "company_norm", "title_norm", "description_clean", "posted_at",
    "location_raw", "eligibility_status", "eligibility_confidence", "eligibility_evidence",
    "timezone_hint", "role_match", "seniority_level", "min_years_required", "role_evidence",
    "salary_status", "min_salary_usd", "max_salary_usd", "salary_period", "salary_raw",
    "tech_stack", "completeness_score", "embedding", "embedding_text",
]

_UPSERT_SQL = f"""
INSERT INTO jobs ({", ".join(_COLUMNS)}, last_seen_at)
VALUES ({", ".join(f"%({c})s" for c in _COLUMNS)}, now())
ON CONFLICT (job_id) DO UPDATE SET
    {", ".join(f"{c} = EXCLUDED.{c}" for c in _COLUMNS if c not in ("job_id",))},
    last_seen_at = now()
"""


def _connect():
    import psycopg2
    return psycopg2.connect(config.SUPABASE_DB_URL)


def _row_from_job(job: dict[str, Any]) -> dict[str, Any]:
    row = {c: job.get(c) for c in _COLUMNS}
    row["eligibility_evidence"] = json.dumps(job.get("eligibility_evidence") or [])
    row["role_evidence"] = json.dumps(job.get("role_evidence") or [])
    row["tech_stack"] = job.get("tech_stack") or []
    row["embedding"] = job.get("embedding")
    return row


def load_to_supabase(jobs: list[dict[str, Any]]) -> int:
    """Upsert jobs into Supabase.

    FUTURE-PROOFING: currently sends all rows in one request, which is fine
    for hundreds of rows. When volume reaches the thousands, batch the
    upsert (e.g. 500 rows per request) and embed in batches to avoid
    request-size limits and timeouts.
    """
    if not jobs:
        raise ValueError("load_to_supabase called with an empty job list; caller must guard this (see main.py)")

    conn = _connect()
    try:
        with conn, conn.cursor() as cur:
            for job in jobs:
                cur.execute(_UPSERT_SQL, _row_from_job(job))
        logger.info("upserted %d job(s) into Supabase", len(jobs))
        return len(jobs)
    finally:
        conn.close()


def delete_replaced(job_ids: list[str]) -> int:
    """Delete rows whose job_id was replaced by a more complete dedup winner (ADR-011)."""
    if not job_ids:
        return 0
    conn = _connect()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("DELETE FROM jobs WHERE job_id = ANY(%s)", (job_ids,))
            deleted = cur.rowcount
        logger.info("deleted %d replaced row(s)", deleted)
        return deleted
    finally:
        conn.close()


def apply_retention(window_days: int = config.WINDOW_DAYS) -> int:
    """Remove rows older than the retention window (ADR-012)."""
    conn = _connect()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "DELETE FROM jobs WHERE posted_at < now() - (%s || ' days')::interval",
                (window_days,),
            )
            deleted = cur.rowcount
        logger.info("retention: removed %d row(s) older than %d days", deleted, window_days)
        return deleted
    finally:
        conn.close()


def fetch_existing_window(window_days: int = config.WINDOW_DAYS) -> list[dict[str, Any]]:
    """Fetch existing rows within the retention window, for dedup clustering
    against the new batch (ADR-011: dedup runs over batch + existing window)."""
    conn = _connect()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT {', '.join(_COLUMNS)} FROM jobs "
                "WHERE posted_at >= now() - (%s || ' days')::interval",
                (window_days,),
            )
            colnames = [desc[0] for desc in cur.description]
            return [dict(zip(colnames, row, strict=True)) for row in cur.fetchall()]
    finally:
        conn.close()
