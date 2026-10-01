"""Remotive public API extractor. No API key required.

NOTE (fixed after live testing): the `search` query parameter did not
filter results as expected (unrelated titles were returned first). We
request the software-dev category, which reliably contains Data
Engineer/ETL postings, and let transform/role_filter.py make the actual
relevance decision rather than pre-filtering on a narrow title substring.
"""
from __future__ import annotations

from rjp.exceptions import ExtractionError, FailureReason
from rjp.extract.base import BaseExtractor
from rjp.utils.http import random_delay, require_keys, request_with_retry

API_URL = "https://remotive.com/api/remote-jobs"
CATEGORY = "software-dev"


class RemotiveExtractor(BaseExtractor):
    name = "remotive"

    def extract(self) -> list[dict]:
        resp = request_with_retry(self.name, "GET", API_URL, params={"category": CATEGORY})
        random_delay()

        try:
            payload = resp.json()
        except ValueError as e:
            raise ExtractionError(self.name, FailureReason.PARSE, f"invalid JSON: {e}") from e

        require_keys(self.name, payload, ["jobs"])

        jobs = []
        for e in payload["jobs"]:
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