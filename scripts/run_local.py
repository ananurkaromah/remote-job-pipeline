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
from rjp.extract.jsearch import JSearchExtractor  # noqa: E402
from rjp.extract.registry import extract_all_sources  # noqa: E402
from rjp.extract.remoteok import RemoteOKExtractor  # noqa: E402
from rjp.extract.remotive import RemotiveExtractor  # noqa: E402
from rjp.transform.pipeline import transform_all  # noqa: E402
from rjp.utils.logging import setup_logging  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="extract + transform only, no writes")
    parser.add_argument(
        "--include-jsearch", action="store_true",
        help="also call JSearch during --dry-run (uses real quota, ignores JSEARCH_RUN_DAYS "
             "if you set JSEARCH_RUN_DAYS to include today for a one-off manual test)",
    )
    args = parser.parse_args()

    setup_logging()

    if args.dry_run:
        extractors = [RemoteOKExtractor(), RemotiveExtractor(), HimalayasExtractor()]
        if args.include_jsearch:
            extractors.append(JSearchExtractor())
        results = extract_all_sources(extractors)
        raw_jobs = [j for r in results for j in r.jobs]
        print(f"Extracted {len(raw_jobs)} raw job(s) from {len(extractors)} source(s).")
        kept, rejected, skipped = transform_all(raw_jobs)
        print(f"Kept {len(kept)}, rejected {len(rejected)}, transform errors {skipped}.")

        if rejected:
            from collections import Counter
            reasons = Counter(r["reason"] for r in rejected)
            print("\nRejection reasons:")
            for reason, count in reasons.most_common():
                print(f"  {reason}: {count}")
            print("\nSample titles per reason (up to 3 each):")
            seen_per_reason: dict[str, int] = {}
            for r in rejected:
                reason = r["reason"]
                if seen_per_reason.get(reason, 0) >= 3:
                    continue
                seen_per_reason[reason] = seen_per_reason.get(reason, 0) + 1
                print(f"  [{reason}] {r.get('title')!r}")

        for job in kept[:5]:
            print(f"  - [{job['eligibility_status']}] {job['title']} @ {job['company']}")
        return

    from rjp.main import run
    sys.exit(run())


if __name__ == "__main__":
    main()