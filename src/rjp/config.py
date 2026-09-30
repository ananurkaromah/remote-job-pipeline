"""Environment-driven configuration. Import this module, never read os.environ elsewhere."""
from __future__ import annotations

import os


def _bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    val = os.environ.get(name)
    return int(val) if val else default


def _float(name: str, default: float) -> float:
    val = os.environ.get(name)
    return float(val) if val else default


# --- Sources ---
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")

# --- Storage (Cloudflare R2) ---
R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET = os.environ.get("R2_BUCKET", "")

# --- Serving (Supabase) ---
SUPABASE_DB_URL = os.environ.get("SUPABASE_DB_URL", "")

# --- Monitoring ---
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

# --- Behavior ---
WINDOW_DAYS = _int("WINDOW_DAYS", 7)
TRANSFORM_FAILURE_THRESHOLD = _float("TRANSFORM_FAILURE_THRESHOLD", 0.30)
MAX_YEARS_REQUIRED_EXCLUSIVE = _int("MAX_YEARS_REQUIRED_EXCLUSIVE", 3)  # ADR-009: 3+ years dropped

# --- JSearch quota (ADR-021) ---
JSEARCH_MAX_REQUESTS_PER_RUN = _int("JSEARCH_MAX_REQUESTS_PER_RUN", 3)
JSEARCH_RUN_DAYS = [d.strip().upper() for d in os.environ.get("JSEARCH_RUN_DAYS", "MON,THU").split(",") if d.strip()]
JSEARCH_QUOTA_RESERVE = _int("JSEARCH_QUOTA_RESERVE", 10)

# --- Selenium (ADR-022, off by default) ---
ENABLE_SELENIUM_SOURCES = _bool("ENABLE_SELENIUM_SOURCES", False)
INSTALL_CHROME = _bool("INSTALL_CHROME", False)

# --- Embedding ---
EMBEDDING_MODEL_NAME = os.environ.get("EMBEDDING_MODEL_NAME", "BAAI/bge-small-en-v1.5")
EMBEDDING_DIMENSIONS = _int("EMBEDDING_DIMENSIONS", 384)

# --- HTTP behavior ---
HTTP_MAX_RETRIES = _int("HTTP_MAX_RETRIES", 3)
HTTP_TIMEOUT_S = _float("HTTP_TIMEOUT_S", 15.0)
HTTP_MIN_DELAY_S = _float("HTTP_MIN_DELAY_S", 0.5)
HTTP_MAX_DELAY_S = _float("HTTP_MAX_DELAY_S", 2.0)
