"""Himalayas job feed extractor. Structured location fields help eligibility.

NOTE: confirmed working via live testing. All jobs are passed through
unfiltered to transform/role_filter.py, consistent with the other
extractors -- title pre-filtering at this layer previously caused valid
adjacent-role postings to be dropped before transform ever saw them.
"""
from __future__ import annotations

from rjp.exceptions import ExtractionError, FailureReason
from rjp.extract.base import BaseExtractor
from rjp.utils.http import random_delay, require_keys, request_with_retry

API_URL = "https://himalayas.app/jobs/api"


class HimalayasExtractor(BaseExtractor):
    name = "himalayas"

    def extract(self) -> list[dict]:
        resp = request_with_retry(self.name, "GET", API_URL, params={"limit": 100})
        random_delay()

        try:
            payload = resp.json()
        except ValueError as e:
            raise ExtractionError(self.name, FailureReason.PARSE, f"invalid JSON: {e}") from e

        require_keys(self.name, payload, ["jobs"])

        jobs = []
        for e in payload["jobs"]:
            company_field = e.get("companyName") or e.get("company")
            if isinstance(company_field, dict):
                company_field = company_field.get("name", "")
            locations = e.get("locationRestrictions") or []
            structured_location = ", ".join(locations) if locations else e.get("locationRestrictionsCategory")
            jobs.append({
                "source": self.name,
                "external_id": str(e.get("guid") or e.get("id")),
                "title": e.get("title"),
                "company": company_field or "",
                "description": e.get("description") or e.get("excerpt", ""),
                "url": e.get("applicationLink") or e.get("url"),
                "posted_at": e.get("pubDate"),
                "location_raw": structured_location,
                "structured_location": structured_location,
                "is_direct_apply_url": False,
                "origin_portal": "himalayas",
            })
        return jobs