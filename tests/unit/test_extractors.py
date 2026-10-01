"""Extractor-level parsing tests using mocked HTTP responses and the real
fixture payloads in tests/fixtures/raw/.

These exist because the 60 transform-layer tests never caught three real
bugs found only during a live run: a dead query parameter (RemoteOK
`tags`), a search parameter that silently didn't filter (Remotive
`search`), and a response envelope that changed shape (JSearch's
/search-v2 nesting jobs under data.jobs instead of data directly). Mocking
the HTTP layer and asserting on parsed output pins today's known-good
field mapping, so a future API change breaks a fast, offline test instead
of only surfacing in a live run.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "raw"


def _load_fixture(name: str):
    with open(FIXTURES / name, encoding="utf-8") as f:
        return json.load(f)


def _mock_response(json_body, status_code: int = 200, headers: dict | None = None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body
    resp.headers = headers or {}
    resp.text = json.dumps(json_body)
    return resp


class TestRemoteOKExtractor:
    def test_parses_fixture_correctly(self):
        from rjp.extract.remoteok import RemoteOKExtractor

        payload = _load_fixture("remoteok.json")
        with patch("rjp.utils.http.requests.request", return_value=_mock_response(payload)):
            jobs = RemoteOKExtractor().extract()

        # The fixture's first element is the legal notice (no "position" key) and
        # must be skipped; both real postings should come through.
        assert len(jobs) == 2
        titles = {j["title"] for j in jobs}
        assert "Data Engineer" in titles
        assert "Senior Backend Engineer" in titles

        de_job = next(j for j in jobs if j["title"] == "Data Engineer")
        assert de_job["source"] == "remoteok"
        assert de_job["company"] == "Acme Analytics"
        assert de_job["location_raw"] == "Worldwide"


class TestRemotiveExtractor:
    def test_parses_fixture_correctly(self):
        from rjp.extract.remotive import RemotiveExtractor

        payload = _load_fixture("remotive.json")
        with patch("rjp.utils.http.requests.request", return_value=_mock_response(payload)):
            jobs = RemotiveExtractor().extract()

        assert len(jobs) == 1
        job = jobs[0]
        assert job["title"] == "Junior Data Engineer"
        assert job["company"] == "Globex"
        assert job["structured_location"] == "APAC"
        assert job["origin_portal"] == "remotive"

    def test_raises_parse_error_on_missing_jobs_key(self):
        from rjp.exceptions import ExtractionError
        from rjp.extract.remotive import RemotiveExtractor
        import pytest

        with patch("rjp.utils.http.requests.request", return_value=_mock_response({"unexpected": "shape"})):
            with pytest.raises(ExtractionError):
                RemotiveExtractor().extract()


class TestHimalayasExtractor:
    def test_parses_fixture_correctly(self):
        from rjp.extract.himalayas import HimalayasExtractor

        payload = _load_fixture("himalayas.json")
        with patch("rjp.utils.http.requests.request", return_value=_mock_response(payload)):
            jobs = HimalayasExtractor().extract()

        assert len(jobs) == 1
        job = jobs[0]
        assert job["title"] == "ETL Developer"
        assert job["company"] == "Initech"
        assert job["structured_location"] == "Worldwide"
        assert job["origin_portal"] == "himalayas"


class TestJSearchExtractor:
    def test_parses_nested_data_jobs_shape(self):
        """Pins the real response envelope confirmed live on 2026-09-30:
        {"status": ..., "data": {"jobs": [...], "cursor": ...}} -- jobs are
        nested under data.jobs, NOT directly under data."""
        from rjp.extract.jsearch import JSearchExtractor

        payload = _load_fixture("jsearch.json")
        with patch("rjp.config.RAPIDAPI_KEY", "test-key"), \
             patch("rjp.utils.http.requests.request", return_value=_mock_response(payload)):
            jobs = JSearchExtractor().extract()

        assert len(jobs) >= 1
        job = jobs[0]
        assert job["title"] == "Data Engineer"
        assert job["company"] == "Umbrella Data"
        assert job["origin_portal"] == "LinkedIn"
        assert job["is_direct_apply_url"] is True

    def test_raises_parse_error_if_data_is_not_a_dict_with_jobs(self):
        """Guards against another envelope change silently returning 0 jobs
        instead of a visible failure (ADR-003: raise, don't swallow)."""
        from rjp.exceptions import ExtractionError
        from rjp.extract.jsearch import JSearchExtractor
        import pytest

        bad_payload = {"status": "OK", "data": ["not", "a", "dict"]}
        with patch("rjp.config.RAPIDAPI_KEY", "test-key"), \
             patch("rjp.utils.http.requests.request", return_value=_mock_response(bad_payload)):
            with pytest.raises(ExtractionError):
                JSearchExtractor().extract()

    def test_missing_api_key_raises_auth_error(self):
        from rjp.exceptions import ExtractionError, FailureReason
        from rjp.extract.jsearch import JSearchExtractor
        import pytest

        with patch("rjp.config.RAPIDAPI_KEY", ""):
            with pytest.raises(ExtractionError) as exc_info:
                JSearchExtractor().extract()
            assert exc_info.value.reason == FailureReason.AUTH