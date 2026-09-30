"""Writes rejected records (filter drops and dedup losers) to R2 for audit (ADR-002)."""
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from rjp import config
from rjp.load.r2 import _client, _partition_key  # reuse the same client/partition scheme
from rjp.utils.logging import get_logger

logger = get_logger(__name__)


def _json_default(obj: Any):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return str(obj)


def write_rejected(rejected: list[dict], run_id: str, run_date: date | None = None) -> str | None:
    if not rejected:
        return None
    run_date = run_date or date.today()
    key = _partition_key("rejected-data", run_date, "rejected.json")
    body = json.dumps({"run_id": run_id, "count": len(rejected), "items": rejected}, default=_json_default).encode()
    _client().put_object(Bucket=config.R2_BUCKET, Key=key, Body=body, ContentType="application/json")
    logger.info("wrote %d rejected record(s) to r2://%s/%s", len(rejected), config.R2_BUCKET, key)
    return key
