from rjp.exceptions import ExtractionError, FailureReason, PartialExtractionError
from rjp.extract.base import BaseExtractor
from rjp.extract.registry import extract_all_sources
from rjp.models import SourceStatus
from rjp.utils.quota import QuotaSkip


class _OkExtractor(BaseExtractor):
    name = "ok_source"

    def extract(self):
        return [{"title": "Data Engineer"}]


class _FailExtractor(BaseExtractor):
    name = "fail_source"

    def extract(self):
        raise ExtractionError(self.name, FailureReason.NETWORK, "timeout")


class _DegradedExtractor(BaseExtractor):
    name = "degraded_source"

    def extract(self):
        raise PartialExtractionError(self.name, FailureReason.QUOTA, [{"title": "partial job"}], "429")


class _SkippedExtractor(BaseExtractor):
    name = "skipped_source"

    def extract(self):
        raise QuotaSkip("not scheduled today")


def test_each_source_attributed_independently():
    results = extract_all_sources([_OkExtractor(), _FailExtractor(), _DegradedExtractor(), _SkippedExtractor()])
    by_name = {r.source: r for r in results}

    assert by_name["ok_source"].status == SourceStatus.OK
    assert len(by_name["ok_source"].jobs) == 1

    assert by_name["fail_source"].status == SourceStatus.FAILED
    assert by_name["fail_source"].reason == "network"

    assert by_name["degraded_source"].status == SourceStatus.DEGRADED
    assert len(by_name["degraded_source"].jobs) == 1

    assert by_name["skipped_source"].status == SourceStatus.SKIPPED


def test_empty_list_is_not_a_failure():
    class _EmptyExtractor(BaseExtractor):
        name = "empty_source"

        def extract(self):
            return []

    results = extract_all_sources([_EmptyExtractor()])
    assert results[0].status == SourceStatus.OK
    assert results[0].jobs == []
