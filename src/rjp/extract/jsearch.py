"""JSearch (RapidAPI) extractor: aggregator API, small free quota (ADR-021).

Quota budgeting is enforced BEFORE calling the API:
  - Only runs on configured weekdays (JSEARCH_RUN_DAYS).
  - Skips entirely if today's data already exists in the raw lake (so a
    manual re-run never burns quota again).
  - Stops issuing queries once the per-run request cap is reached, or once
    the provider's own remaining-quota header falls at/below the reserve.

A `QuotaSkip` raised by the budget check is translated by the registry into
SourceStatus.SKIPPED, not FAILED. If at least one query succeeds before a
429, the extractor raises PartialExtractionError so the jobs already
collected are kept (SourceStatus.DEGRADED).
"""
from __future__ import annotations

from rjp import config
from rjp.exceptions import ExtractionError, FailureReason, PartialExtractionError
from rjp.extract.base import BaseExtractor
from rjp.utils.http import random_delay, request_with_retry
from rjp.utils.logging import get_logger
from rjp.utils.quota import QuotaSkip, RunBudget, already_extracted_today

logger = get_logger(__name__)

API_URL = "https://jsearch.p.rapidapi.com/search"
QUERIES = ["data engineer remote", "etl developer remote", "junior data engineer remote"]


class JSearchExtractor(BaseExtractor):
    name = "jsearch"

    def __init__(self, run_envelope: dict | None = None):
        self.run_envelope = run_envelope

    def extract(self) -> list[dict]:
        if not config.RAPIDAPI_KEY:
            raise ExtractionError(self.name, FailureReason.AUTH, "RAPIDAPI_KEY not set")

        if already_extracted_today(self.name, self.run_envelope):
            raise QuotaSkip("already extracted successfully today")

        budget = RunBudget.from_config()
        budget.check_scheduled_today()

        headers = {
            "X-RapidAPI-Key": config.RAPIDAPI_KEY,
            "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
        }

        jobs: list[dict] = []
        queries_run = 0
        for query in QUERIES:
            if not budget.can_make_request():
                logger.info("source=%s stopping: per-run request budget reached", self.name)
                break
            try:
                resp = request_with_retry(
                    self.name, "GET", API_URL,
                    headers=headers, params={"query": query, "date_posted": "week"},
                    max_retries=1,  # never retry a quota-limited call; budget instead
                )
            except ExtractionError as e:
                budget.record_request()
                queries_run += 1
                if e.reason == FailureReason.QUOTA:
                    if jobs:
                        raise PartialExtractionError(self.name, FailureReason.QUOTA, jobs, str(e)) from e
                    raise
                raise

            budget.record_request()
            queries_run += 1
            random_delay()

            try:
                payload = resp.json()
            except ValueError as e:
                raise ExtractionError(self.name, FailureReason.PARSE, f"invalid JSON: {e}") from e

            remaining = resp.headers.get("X-RateLimit-Requests-Remaining")
            if remaining is not None:
                try:
                    budget.remaining_quota = int(remaining)
                except ValueError:
                    pass

            for e_job in payload.get("data", []):
                jobs.append({
                    "source": self.name,
                    "external_id": e_job.get("job_id"),
                    "title": e_job.get("job_title"),
                    "company": e_job.get("employer_name"),
                    "description": e_job.get("job_description", ""),
                    "url": e_job.get("job_apply_link"),
                    "posted_at": e_job.get("job_posted_at_datetime_utc"),
                    "location_raw": e_job.get("job_country"),
                    "structured_location": e_job.get("job_country"),
                    "is_direct_apply_url": bool(e_job.get("job_apply_is_direct", False)),
                    "origin_portal": e_job.get("job_publisher"),
                })

        logger.info("source=%s queries_run=%d jobs=%d", self.name, queries_run, len(jobs))
        return jobs
