"""RemoteOK public JSON API extractor. No API key required.

NOTE (fixed after live testing): the `tags` query parameter does not filter
server-side as documented and returns a near-empty payload. We fetch the
unfiltered recent feed instead and let transform/role_filter.py -- which
already knows about adjacent titles like "Analytics Engineer" or "Data
Pipeline Engineer" -- make the relevance decision. Filtering by a narrow
title substring here would silently drop valid adjacent-role postings
before they ever reach that logic.
"""
from __future__ import annotations

from rjp.exceptions import ExtractionError, FailureReason
from rjp.extract.base import BaseExtractor
from rjp.utils.http import random_delay, request_with_retry

API_URL = "https://remoteok.com/api"


class RemoteOKExtractor(BaseExtractor):
    name = "remoteok"

    def extract(self) -> list[dict]:
        resp = request_with_retry(self.name, "GET", API_URL)
        random_delay()

        try:
            payload = resp.json()
        except ValueError as e:
            raise ExtractionError(self.name, FailureReason.PARSE, f"invalid JSON: {e}") from e

        if not isinstance(payload, list):
            raise ExtractionError(self.name, FailureReason.PARSE, "expected a JSON list")

        # RemoteOK's first element is a legal notice, not a job; skip it.
        entries = [e for e in payload if isinstance(e, dict) and "id" in e and "position" in e]

        jobs = []
        for e in entries:
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