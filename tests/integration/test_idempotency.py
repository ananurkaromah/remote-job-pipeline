"""Integration test: running the pipeline twice must leave the database unchanged.

Requires live SUPABASE_DB_URL, R2, and RAPIDAPI_KEY credentials, so this is
skipped automatically unless RUN_INTEGRATION_TESTS=1 is set (ADR-015).
This is NOT run in CI by default; run it manually before scheduling the
pipeline for the first time (see docs/deployment.md section 8).
"""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "1",
    reason="set RUN_INTEGRATION_TESTS=1 and configure real credentials to run this test",
)


def test_running_pipeline_twice_is_idempotent():
    import psycopg2

    from rjp import config
    from rjp.main import run

    exit_code_1 = run()
    assert exit_code_1 in (0, 1)

    conn = psycopg2.connect(config.SUPABASE_DB_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*), max(last_seen_at) FROM jobs")
            count_1, last_seen_1 = cur.fetchone()
    finally:
        conn.close()

    exit_code_2 = run()
    assert exit_code_2 in (0, 1)

    conn = psycopg2.connect(config.SUPABASE_DB_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM jobs")
            count_2, = cur.fetchone()
    finally:
        conn.close()

    assert count_1 == count_2, "row count changed after a second run on the same data"
