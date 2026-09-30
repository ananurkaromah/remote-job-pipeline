"""Discord webhook notifications: never raises, short timeout (ADR-004, ADR-017)."""
from __future__ import annotations

import requests

from rjp import config
from rjp.models import RunSummary
from rjp.monitoring.formatting import format_summary
from rjp.utils.logging import get_logger

logger = get_logger(__name__)

_TIMEOUT_S = 5.0


def _send(content_lines: str, color: int) -> None:
    if not config.DISCORD_WEBHOOK_URL:
        logger.warning("DISCORD_WEBHOOK_URL not set; skipping notification:\n%s", content_lines)
        return
    payload = {"embeds": [{"description": content_lines, "color": color}]}
    try:
        requests.post(config.DISCORD_WEBHOOK_URL, json=payload, timeout=_TIMEOUT_S)
    except requests.RequestException as e:
        logger.warning("failed to send Discord notification: %s", e)


def notify_run_summary(summary: RunSummary) -> None:
    content, color = format_summary(summary)
    _send(content, color)


def notify_warning(message: str, run_id: str = "") -> None:
    prefix = f"**remote-job-pipeline** | run `{run_id}`\n" if run_id else "**remote-job-pipeline**\n"
    _send(prefix + message, 0xF1C40F)


def notify_failure(message: str, run_id: str = "") -> None:
    prefix = f"**remote-job-pipeline** | run `{run_id}`\n" if run_id else "**remote-job-pipeline**\n"
    _send(prefix + message, 0xE74C3C)
