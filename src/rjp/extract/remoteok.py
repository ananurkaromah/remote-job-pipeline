"""RemoteOK public JSON API extractor. No API key required."""
from __future__ import annotations

from rjp.exceptions import ExtractionError, FailureReason
from rjp.extract.base import BaseExtractor
from rjp.utils.http import random_delay, request_with_retry

API_URL = "https://remoteok.com/api"
SEARCH_TERMS = ("data engineer", "etl")


class RemoteOKExtractor(BaseExtractor):
    name = "remoteok"

    def extract(self) -> list[dict]:
        resp = request_with_retry(self.name, "GET", API_URL, params={"tags": "data-engineer"})
        random_delay()

        try:
            payload = resp.json()
        except ValueError as e:
            raise ExtractionError(self.name, FailureReason.PARSE, f"invalid JSON: {e}") from e

        if not isinstance(payload, list):
            raise ExtractionError(self.name, FailureReason.PARSE, "expected a JSON list")

        # RemoteOK's first element is a legal notice, not a job; skip it if present.
        entries = [e for e in payload if isinstance(e, dict) and "id" in e and "position" in e]

        jobs = []
        for e in entries:
            title = (e.get("position") or "").lower()
            if not any(term in title for term in SEARCH_TERMS):
                continue
            jobs.append({
                "source": self.name,
                "external_id": str(e.get("id")),
                "title": e.get("position"),
                "company": e.get("company"),
                "description": e.get("description", ""),
                "url": e.get("url") or f"https://remoteok.com/l/{e.get('id')}",
                "posted_at": e.get("date"),
                "location_raw": e.get("location"),
                "structured_location": e.get("location"),
                "is_direct_apply_url": False,
                "origin_portal": "remoteok",
            })
        return jobs
