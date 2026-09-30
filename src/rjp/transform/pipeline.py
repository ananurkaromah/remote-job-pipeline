"""Per-job transform orchestration (ADR-016).

Each job is transformed inside its own try/except. The error label is only
computed after isinstance(job, dict), because a fully corrupt job (e.g.
None) would otherwise raise a second exception inside the except block and
hide the original error.
"""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

from rjp import config
from rjp.models import utcnow
from rjp.transform.cleaning import clean_description
from rjp.transform.dedup import completeness_score
from rjp.transform.eligibility import classify_eligibility
from rjp.transform.normalization import canonical_url, normalize_company, normalize_title
from rjp.transform.role_filter import classify
from rjp.transform.salary import parse_salary
from rjp.transform.tech_stack import extract_tech_stack
from rjp.utils.logging import get_logger

logger = get_logger(__name__)


class DropJob(Exception):
    """Raised internally to short-circuit a job that failed a filter, with a reason."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def make_job_id(source: str, external_id: str | None, url: str | None) -> str:
    basis = f"{source}:{external_id}" if external_id else f"{source}:{canonical_url(url or '')}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def _parse_posted_at(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
    if isinstance(raw, (int, float)):
        return datetime.fromtimestamp(raw, tz=UTC)
    if isinstance(raw, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(raw, fmt)
                return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
            except ValueError:
                continue
    return None


def transform_one(job: dict) -> dict:
    """Transform a single raw job into the schema stored in Supabase.

    Raises DropJob(reason) for jobs that fail a filter (too old, wrong role,
    senior, restricted-and-configured-to-drop). Everything else propagates
    as a normal exception, to be caught by transform_all's per-job guard.
    """
    title = job.get("title") or ""
    company = job.get("company") or ""
    description_raw = job.get("description") or ""
    url = job.get("url") or ""
    source = job.get("source") or "unknown"

    posted_at = _parse_posted_at(job.get("posted_at")) or utcnow()
    cutoff = utcnow() - timedelta(days=config.WINDOW_DAYS)
    if posted_at < cutoff:
        raise DropJob("too_old")

    description_clean = clean_description(description_raw)

    role_decision = classify(title, description_clean)
    if not role_decision.keep:
        raise DropJob(role_decision.reason)

    eligibility = classify_eligibility(
        title=title,
        description=description_clean,
        structured_location=job.get("structured_location"),
    )

    salary = parse_salary(description_clean)
    tech_stack = extract_tech_stack(f"{title}\n{description_clean}")

    job_id = make_job_id(source, job.get("external_id"), url)

    result = {
        "job_id": job_id,
        "source": source,
        "origin_portal": job.get("origin_portal"),
        "external_id": job.get("external_id"),
        "url": url,
        "canonical_url": canonical_url(url),
        "is_direct_apply_url": bool(job.get("is_direct_apply_url", False)),
        "title": title,
        "company": company,
        "company_norm": normalize_company(company),
        "title_norm": normalize_title(title),
        "description_clean": description_clean,
        "posted_at": posted_at,
        "location_raw": job.get("location_raw"),
        "eligibility_status": eligibility.status,
        "eligibility_confidence": eligibility.confidence,
        "eligibility_evidence": eligibility.evidence,
        "timezone_hint": eligibility.timezone_hint,
        "role_match": role_decision.role_match,
        "seniority_level": role_decision.seniority,
        "min_years_required": role_decision.min_years_required,
        "role_evidence": role_decision.evidence,
        "salary_status": salary.status,
        "min_salary_usd": salary.min_usd,
        "max_salary_usd": salary.max_usd,
        "salary_period": salary.period,
        "salary_raw": salary.raw,
        "tech_stack": tech_stack,
    }
    result["completeness_score"] = completeness_score(result)
    return result


def transform_all(raw_jobs: list) -> tuple[list[dict], list[dict], int]:
    """Transform every raw job. Returns (kept, rejected, skipped_error_count).

    `rejected` holds jobs dropped by a filter, each tagged with a reason, for
    the rejected-data/ audit trail. `skipped_error_count` counts jobs that
    raised an unexpected exception (not a normal filter drop).
    """
    kept: list[dict] = []
    rejected: list[dict] = []
    skipped = 0

    for job in raw_jobs:
        try:
            kept.append(transform_one(job))
        except DropJob as e:
            label = job.get("title", "unknown") if isinstance(job, dict) else f"<{type(job).__name__}>"
            rejected.append({"title": label, "reason": e.reason, "raw": job if isinstance(job, dict) else None})
        except Exception:
            skipped += 1
            # Never call .get() before checking isinstance: a fully corrupt
            # job (e.g. None) must not raise a second exception here and
            # hide the original error.
            label = job.get("id", "unknown") if isinstance(job, dict) else f"<{type(job).__name__}>"
            logger.exception("transform failed for job=%s", label)

    total = len(raw_jobs)
    logger.info("%d/%d job(s) failed transformation and were skipped", skipped, total)

    if total > 0 and (skipped / total) > config.TRANSFORM_FAILURE_THRESHOLD:
        logger.error(
            "transform failure ratio %.2f exceeds threshold %.2f -- likely a source format change",
            skipped / total, config.TRANSFORM_FAILURE_THRESHOLD,
        )

    return kept, rejected, skipped
