#!/usr/bin/env python3
"""Rebuild transformed data from the raw lake without calling any source API again.

Usage:
    python scripts/reprocess_from_r2.py --date 2026-09-29
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rjp.load.r2 import get_json  # noqa: E402
from rjp.transform.pipeline import transform_all  # noqa: E402
from rjp.utils.logging import setup_logging  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYY-MM-DD partition to reprocess")
    args = parser.parse_args()

    setup_logging()
    d = datetime.strptime(args.date, "%Y-%m-%d").date()
    key = f"raw-data/year={d.year:04d}/month={d.month:02d}/day={d.day:02d}/jobs.json"

    envelope = get_json(key)
    if envelope is None:
        print(f"No raw data found at {key}", file=sys.stderr)
        sys.exit(1)

    raw_jobs = envelope.get("jobs", [])
    print(f"Loaded {len(raw_jobs)} raw job(s) from {key}")
    kept, rejected, skipped = transform_all(raw_jobs)
    print(f"Kept {len(kept)}, rejected {len(rejected)}, transform errors {skipped}.")
    print("Reprocessing does not upsert to Supabase by default; wire this into main.py's")
    print("load stage if you want a full rebuild to also update the database.")


if __name__ == "__main__":
    main()
