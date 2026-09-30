"""Cross-source deduplication: keep the most complete record (ADR-010, ADR-011).

Clustering, from most to least certain:
  1. Same canonical URL.
  2. Same company_norm + title_norm.
  3. Same company_norm, fuzzy title match, AND description similarity above
     threshold (prevents merging the same title at the same company posted
     for different regions).

Within a cluster, a single winner is chosen by a deterministic total order
so that re-running the pipeline on the same data always picks the same
winner (idempotency, ADR-015). Losers are not merged; they are dropped and
should be written to rejected-data/ with duplicate_of by the caller.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

SOURCE_PRIORITY = {"company_careers": 3, "himalayas": 2, "remotive": 2, "remoteok": 2, "jsearch": 1}

TITLE_FUZZY_THRESHOLD = 0.90
DESCRIPTION_JACCARD_THRESHOLD = 0.80


def _title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def is_duplicate(job_a: dict, job_b: dict) -> bool:
    """Conservative duplicate check: prefer a missed duplicate over a false merge."""
    url_a, url_b = job_a.get("canonical_url", ""), job_b.get("canonical_url", "")
    if url_a and url_b and url_a == url_b:
        return True

    company_a, company_b = job_a.get("company_norm", ""), job_b.get("company_norm", "")
    if not company_a or company_a != company_b:
        return False

    title_a, title_b = job_a.get("title_norm", ""), job_b.get("title_norm", "")
    if title_a == title_b and title_a:
        # Same company + exact same normalized title: still check description
        # when both are present, so postings for different regions aren't merged.
        desc_a, desc_b = job_a.get("description_clean", ""), job_b.get("description_clean", "")
        if desc_a and desc_b:
            return _jaccard(desc_a, desc_b) >= DESCRIPTION_JACCARD_THRESHOLD
        return True

    if _title_similarity(title_a, title_b) >= TITLE_FUZZY_THRESHOLD:
        desc_a, desc_b = job_a.get("description_clean", ""), job_b.get("description_clean", "")
        if desc_a and desc_b:
            return _jaccard(desc_a, desc_b) >= DESCRIPTION_JACCARD_THRESHOLD
        # No description on one side: require exact eligibility match as a
        # more conservative fallback signal.
        return job_a.get("eligibility_status") == job_b.get("eligibility_status")

    return False


def completeness_score(job: dict) -> int:
    score = 0
    score += min(len(job.get("description_clean") or "") // 500, 6)
    score += {"disclosed": 3, "partial": 2}.get(job.get("salary_status"), 0)
    score += 2 if job.get("eligibility_status") in ("eligible", "restricted") else 0
    score += 2 if job.get("location_raw") else 0
    score += min(len(job.get("tech_stack") or []), 4)
    score += 2 if job.get("posted_at") else 0
    score += 1 if job.get("company") else 0
    score += 2 if job.get("is_direct_apply_url") else 0
    return score


def _winner_key(job: dict):
    posted_at = job.get("posted_at")
    posted_ts = posted_at.timestamp() if posted_at is not None else 0
    return (
        -completeness_score(job),
        -SOURCE_PRIORITY.get(job.get("source", ""), 0),
        -posted_ts,
        job.get("job_id", ""),
    )


def cluster_jobs(jobs: list[dict]) -> list[list[dict]]:
    """Group jobs into duplicate clusters, blocking on company_norm for efficiency."""
    blocks: dict[str, list[dict]] = {}
    for job in jobs:
        blocks.setdefault(job.get("company_norm", ""), []).append(job)

    clusters: list[list[dict]] = []
    for _, block in blocks.items():
        assigned = [False] * len(block)
        for i in range(len(block)):
            if assigned[i]:
                continue
            cluster = [block[i]]
            assigned[i] = True
            for j in range(i + 1, len(block)):
                if assigned[j]:
                    continue
                if any(is_duplicate(block[j], member) for member in cluster):
                    cluster.append(block[j])
                    assigned[j] = True
            clusters.append(cluster)
    return clusters


def deduplicate(jobs: list[dict]) -> tuple[list[dict], list[dict]]:
    """Return (winners, losers). Losers carry duplicate_of pointing at the winner's job_id."""
    winners: list[dict] = []
    losers: list[dict] = []
    for cluster in cluster_jobs(jobs):
        if len(cluster) == 1:
            winners.append(cluster[0])
            continue
        ordered = sorted(cluster, key=_winner_key)
        winner, rest = ordered[0], ordered[1:]
        winners.append(winner)
        for loser in rest:
            loser = dict(loser)
            loser["duplicate_of"] = winner.get("job_id")
            losers.append(loser)
    return winners, losers
