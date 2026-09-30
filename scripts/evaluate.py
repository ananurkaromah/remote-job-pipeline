#!/usr/bin/env python3
"""Evaluate transform rules against the labeled sets in tests/labeled/.

Usage:
    python scripts/evaluate.py eligibility
    python scripts/evaluate.py role
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rjp.transform.eligibility import classify_eligibility  # noqa: E402
from rjp.transform.role_filter import classify as classify_role_and_seniority  # noqa: E402

LABELED_DIR = Path(__file__).resolve().parent.parent / "tests" / "labeled"


def _load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def evaluate_eligibility() -> None:
    rows = _load_jsonl(LABELED_DIR / "eligibility_labeled.jsonl")
    confusion: Counter = Counter()
    for row in rows:
        result = classify_eligibility(
            title=row.get("title", ""), description=row.get("description", ""),
            structured_location=row.get("structured_location"),
        )
        confusion[(row["label"], result.status)] += 1

    print(f"{len(rows)} labeled example(s)")
    print("(true_label, predicted) -> count")
    for k, v in sorted(confusion.items()):
        print(f"  {k}: {v}")

    tp = confusion[("eligible", "eligible")]
    fp = sum(v for (t, p), v in confusion.items() if p == "eligible" and t != "eligible")
    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    print(f"\nprecision(eligible) = {precision:.2f}" if tp + fp else "\nprecision(eligible): no predictions")

    tp_r = confusion[("restricted", "restricted")]
    fn_r = sum(v for (t, p), v in confusion.items() if t == "restricted" and p != "restricted")
    recall_r = tp_r / (tp_r + fn_r) if (tp_r + fn_r) else float("nan")
    print(f"recall(restricted)  = {recall_r:.2f}" if tp_r + fn_r else "recall(restricted): no restricted examples")


def evaluate_role() -> None:
    rows = _load_jsonl(LABELED_DIR / "role_labeled.jsonl")
    correct = 0
    for row in rows:
        decision = classify_role_and_seniority(row.get("title", ""), row.get("description", ""))
        predicted_keep = decision.keep
        if predicted_keep == row["keep"]:
            correct += 1
        else:
            print(f"MISMATCH title={row['title']!r} expected keep={row['keep']} got keep={predicted_keep} ({decision.reason})")
    print(f"\n{correct}/{len(rows)} correct ({correct / len(rows):.0%})" if rows else "no labeled rows")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", choices=["eligibility", "role"])
    args = parser.parse_args()
    {"eligibility": evaluate_eligibility, "role": evaluate_role}[args.target]()


if __name__ == "__main__":
    main()
