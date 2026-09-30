"""HTTP helpers shared by extractors: UA rotation, random delay, retry with backoff."""
from __future__ import annotations

import random
import time
from typing import Any

import requests

from rjp import config
from rjp.exceptions import ExtractionError, FailureReason
from rjp.utils.logging import get_logger

logger = get_logger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36",
]

# Status codes worth retrying: transient server-side or rate-limit issues.
RETRYABLE_STATUS = {500, 502, 503, 504}


def random_headers() -> dict[str, str]:
    return {"User-Agent": random.choice(USER_AGENTS)}


def random_delay(min_s: float = config.HTTP_MIN_DELAY_S, max_s: float = config.HTTP_MAX_DELAY_S) -> None:
    time.sleep(random.uniform(min_s, max_s))


def request_with_retry(
    source: str,
    method: str,
    url: str,
    max_retries: int = config.HTTP_MAX_RETRIES,
    **kwargs: Any,
) -> requests.Response:
    """GET/POST with exponential backoff on transient failures.

    Raises ExtractionError(source, ...) on anything non-transient or after
    retries are exhausted. 429 raises immediately as QUOTA (never retried,
    per ADR-021: quota-limited sources budget requests instead of retrying).
    """
    headers = kwargs.pop("headers", {}) or {}
    headers = {**random_headers(), **headers}
    timeout = kwargs.pop("timeout", config.HTTP_TIMEOUT_S)

    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.request(method, url, headers=headers, timeout=timeout, **kwargs)
        except requests.RequestException as e:
            last_exc = e
            logger.warning("source=%s network error attempt=%d/%d: %s", source, attempt, max_retries, e)
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            raise ExtractionError(source, FailureReason.NETWORK, str(e)) from e

        if resp.status_code in (401, 403):
            raise ExtractionError(source, FailureReason.AUTH, f"HTTP {resp.status_code}")
        if resp.status_code == 429:
            raise ExtractionError(source, FailureReason.QUOTA, "HTTP 429 rate limited / quota exhausted")
        if resp.status_code in RETRYABLE_STATUS:
            logger.warning(
                "source=%s retryable status=%d attempt=%d/%d", source, resp.status_code, attempt, max_retries
            )
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            raise ExtractionError(source, FailureReason.HTTP_STATUS, f"HTTP {resp.status_code} after retries")
        if resp.status_code >= 400:
            raise ExtractionError(source, FailureReason.HTTP_STATUS, f"HTTP {resp.status_code}")

        return resp

    raise ExtractionError(source, FailureReason.NETWORK, str(last_exc) if last_exc else "unknown")


def require_keys(source: str, payload: dict, keys: list[str]) -> None:
    """Validate response shape at the extractor boundary (ADR-003).

    A 200 OK whose body is missing expected keys must not look like "0 jobs".
    """
    missing = [k for k in keys if k not in payload]
    if missing:
        raise ExtractionError(source, FailureReason.PARSE, f"missing keys: {missing}")
