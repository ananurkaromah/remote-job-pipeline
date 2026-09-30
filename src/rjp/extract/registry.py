"""Per-source failure attribution (ADR-003, ADR-021)."""
from __future__ import annotations

import time

from rjp.exceptions import ExtractionError, PartialExtractionError
from rjp.extract.base import BaseExtractor
from rjp.models import SourceResult, SourceStatus
from rjp.utils.logging import get_logger
from rjp.utils.quota import QuotaSkip

logger = get_logger(__name__)


def extract_all_sources(extractors: list[BaseExtractor]) -> list[SourceResult]:
    results: list[SourceResult] = []
    for ex in extractors:
        start = time.monotonic()
        try:
            jobs = ex.extract()
            duration = time.monotonic() - start
            results.append(SourceResult(ex.name, SourceStatus.OK, jobs, None, "", duration))
            logger.info("source=%s ok jobs=%d duration_s=%.2f", ex.name, len(jobs), duration)

        except QuotaSkip as e:
            duration = time.monotonic() - start
            results.append(SourceResult(ex.name, SourceStatus.SKIPPED, [], "skip", str(e), duration))
            logger.info("source=%s skipped reason=%s", ex.name, e)

        except PartialExtractionError as e:
            duration = time.monotonic() - start
            results.append(
                SourceResult(ex.name, SourceStatus.DEGRADED, e.jobs, e.reason.value, e.detail, duration)
            )
            logger.warning(
                "source=%s DEGRADED reason=%s detail=%s kept=%d", ex.name, e.reason.value, e.detail, len(e.jobs)
            )

        except ExtractionError as e:
            duration = time.monotonic() - start
            results.append(SourceResult(ex.name, SourceStatus.FAILED, [], e.reason.value, e.detail, duration))
            logger.error("source=%s FAILED reason=%s detail=%s", ex.name, e.reason.value, e.detail)

        except Exception as e:  # unexpected bug inside an extractor
            duration = time.monotonic() - start
            results.append(SourceResult(ex.name, SourceStatus.FAILED, [], "parse", repr(e), duration))
            logger.exception("source=%s crashed unexpectedly", ex.name)

    return results
