# Evaluation

Claims like "filters for Indonesia" are only credible with measurement
(ADR-020). Run:

```bash
python scripts/evaluate.py eligibility
python scripts/evaluate.py role
```

## Current results (starter labeled sets)

These sets are intentionally small (20-24 rows each) as a starting point.
Expand `tests/labeled/*.jsonl` as real postings are seen, aiming for
100-150 eligibility rows and about 100 role rows (ADR-020).

```text
$ python scripts/evaluate.py eligibility
20 labeled example(s)
precision(eligible) = 0.88
recall(restricted)  = 0.86

$ python scripts/evaluate.py role
24/24 correct (100%)
```

## What to track over time

- **precision(eligible)** — the most important metric: a wrong `eligible`
  wastes the user's time applying to a role they can't take.
- **recall(restricted)** — a missed restriction is less costly (the user
  just doesn't get the job) but still worth tracking.
- **role classification accuracy** — especially the years-of-experience
  edge cases in `tests/unit/test_role_filter.py`.
- **dedup precision** — `tests/labeled/dedup_pairs.jsonl` has a starter set
  including hard negatives (same company, different region). A false merge
  is worse than a missed duplicate (ADR-010).
- **unknown-eligibility rate** and **skipped-transform rate** in the
  Discord run summary, over time, not just per run.

Adding a new labeled example is as simple as appending a line to the
relevant `.jsonl` file in `tests/labeled/` and re-running the script.
