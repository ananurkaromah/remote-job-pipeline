#!/usr/bin/env python3
"""Apply sql/*.sql migrations in order against SUPABASE_DB_URL.

Usage:
    export SUPABASE_DB_URL="postgresql://postgres:...@...supabase.com:5432/postgres"
    python scripts/apply_sql.py
    python scripts/apply_sql.py --only 006_roles.sql   # apply one file only
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rjp import config  # noqa: E402

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="apply a single migration file by name")
    args = parser.parse_args()

    if not config.SUPABASE_DB_URL:
        print("SUPABASE_DB_URL is not set.", file=sys.stderr)
        sys.exit(1)

    import psycopg2

    files = sorted(SQL_DIR.glob("*.sql"))
    if args.only:
        files = [f for f in files if f.name == args.only]
        if not files:
            print(f"No migration named {args.only!r} found in {SQL_DIR}", file=sys.stderr)
            sys.exit(1)

    conn = psycopg2.connect(config.SUPABASE_DB_URL)
    try:
        with conn, conn.cursor() as cur:
            for f in files:
                print(f"Applying {f.name} ...")
                cur.execute(f.read_text(encoding="utf-8"))
        print(f"Applied {len(files)} migration(s).")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
