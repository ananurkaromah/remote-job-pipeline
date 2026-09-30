#!/usr/bin/env python3
"""Example hybrid search query against search_jobs(), for demos.

Usage:
    python scripts/sample_search.py "junior data engineer with airflow and spark"
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rjp import config  # noqa: E402
from rjp.embed.encoder import encode_query  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/sample_search.py \"<your query>\"", file=sys.stderr)
        sys.exit(1)

    query = sys.argv[1]
    embedding = encode_query(query)

    import psycopg2

    conn = psycopg2.connect(config.SUPABASE_DB_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT title, company, eligibility_status, similarity "
                "FROM search_jobs(%s::vector, %s, %s, %s, %s, %s)",
                (embedding, ["eligible", "unknown"], [], None, True, 10),
            )
            for row in cur.fetchall():
                print(row)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
