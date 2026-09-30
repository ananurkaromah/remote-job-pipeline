"""Remotive public API extractor. No API key required."""
from __future__ import annotations

from rjp.exceptions import ExtractionError, FailureReason
from rjp.extract.base import BaseExtractor
from rjp.utils.http import random_delay, request_with_retry, require_keys

API_URL = "https://remotive.com/api/remote-jobs"
CATEGORY = "software-dev"
SEARCH_TERMS = ("data engineer", "etl")


class RemotiveExtractor(BaseExtractor):
    name = "remotive"

    def extract(self) -> list[dict]:
        resp = request_with_retry(self.name, "GET", API_URL, params={"search": "data engineer"})
        random_delay()

        try:
            payload = resp.json()
        except ValueError as e:
            raise ExtractionError(self.name, FailureReason.PARSE, f"invalid JSON: {e}") from e

        require_keys(self.name, payload, ["jobs"])

        jobs = []
        for e in payload["jobs"]:
            title = (e.get("title") or "").lower()
            if not any(term in title for term in SEARCH_TERMS):
                continue
            jobs.append({
                "source": self.name,
                "external_id": str(e.get("id")),
                "title": e.get("title"),
                "company": e.get("company_name"),
                "description": e.get("description", ""),
                "url": e.get("url"),
                "posted_at": e.get("publication_date"),
                "location_raw": e.get("candidate_required_location"),
                "structured_location": e.get("candidate_required_location"),
                "is_direct_apply_url": False,
                "origin_portal": "remotive",
            })
        return jobs
