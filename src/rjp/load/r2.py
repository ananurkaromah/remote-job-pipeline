"""Cloudflare R2 raw data lake (ADR-025): S3-compatible, boto3-based.

Replaces Google Cloud Storage (ADR-002 storage-agnostic layering meant only
this module needed to change). Partition layout, run envelope, and the
overwrite-by-partition rule are unchanged from the original GCS design.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from functools import lru_cache
from typing import Any

from rjp import config
from rjp.utils.logging import get_logger

logger = get_logger(__name__)


def _json_default(obj: Any):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return str(obj)


@lru_cache(maxsize=1)
def _client():
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=f"https://{config.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=config.R2_ACCESS_KEY_ID,
        aws_secret_access_key=config.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def _partition_key(prefix: str, run_date: date, filename: str) -> str:
    return f"{prefix}/year={run_date.year:04d}/month={run_date.month:02d}/day={run_date.day:02d}/{filename}"


def object_exists(key: str) -> bool:
    from botocore.exceptions import ClientError
    try:
        _client().head_object(Bucket=config.R2_BUCKET, Key=key)
        return True
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") in ("404", "NoSuchKey"):
            return False
        raise


def get_json(key: str) -> dict | None:
    from botocore.exceptions import ClientError
    try:
        obj = _client().get_object(Bucket=config.R2_BUCKET, Key=key)
        return json.loads(obj["Body"].read())
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") in ("404", "NoSuchKey"):
            return None
        raise


def get_today_envelope(run_date: date | None = None) -> dict | None:
    """Read today's raw-data envelope, if any -- used by quota-aware sources
    to skip a re-run that already has healthy data for today (ADR-021)."""
    run_date = run_date or date.today()
    key = _partition_key("raw-data", run_date, "jobs.json")
    return get_json(key)


def load_raw_to_r2(jobs: list[dict], envelope_meta: dict, run_date: date | None = None, partial: bool = False) -> str:
    """Write the raw run envelope. Never overwrites a good file with an empty result.

    FUTURE-PROOFING: currently sends the whole payload in one PutObject call,
    which is fine for hundreds of rows. When volume reaches the thousands,
    consider splitting into multiple objects to avoid single-object size and
    request-time limits.
    """
    if not jobs:
        raise ValueError("load_raw_to_r2 called with an empty job list; caller must guard this (see main.py)")

    run_date = run_date or date.today()
    envelope = {**envelope_meta, "jobs": jobs}
    body = json.dumps(envelope, default=_json_default).encode("utf-8")

    filename = f"jobs.{envelope_meta.get('run_id', 'run')}.partial.json" if partial else "jobs.json"
    key = _partition_key("raw-data", run_date, filename)

    if not partial and object_exists(key):
        logger.warning("raw-data key %s already exists; overwriting with today's latest full run", key)

    _client().put_object(Bucket=config.R2_BUCKET, Key=key, Body=body, ContentType="application/json")
    logger.info("wrote %d job(s) to r2://%s/%s", len(jobs), config.R2_BUCKET, key)
    return key


def list_raw_dates() -> list[str]:
    """List year=/month=/day= prefixes under raw-data/, for reprocessing."""
    paginator = _client().get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=config.R2_BUCKET, Prefix="raw-data/"):
        for obj in page.get("Contents", []):
            keys.append(obj["Key"])
    return keys
