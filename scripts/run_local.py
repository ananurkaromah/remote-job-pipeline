#!/usr/bin/env python3
"""Run the pipeline locally.

Usage:
    python scripts/run_local.py             # full run against real services
    python scripts/run_local.py --dry-run   # extract + transform only, no writes
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rjp.extract.himalayas import HimalayasExtractor  # noqa: E402
from rjp.extract.registry import extract_all_sources  # noqa: E402
from rjp.extract.remoteok import RemoteOKExtractor  # noqa: E402
from rjp.extract.remotive import RemotiveExtractor  # noqa: E402
from rjp.transform.pipeline import transform_all  # noqa: E402
from rjp.utils.logging import setup_logging  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="extract + transform only, no writes")
    args = parser.parse_args()

    setup_logging()

    if args.dry_run:
        extractors = [RemoteOKExtractor(), RemotiveExtractor(), HimalayasExtractor()]
        results = extract_all_sources(extractors)
        raw_jobs = [j for r in results for j in r.jobs]
        print(f"Extracted {len(raw_jobs)} raw job(s) from {len(extractors)} source(s).")
        kept, rejected, skipped = transform_all(raw_jobs)
        print(f"Kept {len(kept)}, rejected {len(rejected)}, transform errors {skipped}.")
        for job in kept[:5]:
            print(f"  - [{job['eligibility_status']}] {job['title']} @ {job['company']}")
        return

    from rjp.main import run
    sys.exit(run())


if __name__ == "__main__":
    main()
