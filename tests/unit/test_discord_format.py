from rjp.models import RunSummary, SourceResult, SourceStatus
from rjp.monitoring.formatting import classify_summary


def test_all_failed_is_failure_color():
    summary = RunSummary(run_id="abc", source_results=[
        SourceResult("remoteok", SourceStatus.FAILED, reason="network"),
        SourceResult("remotive", SourceStatus.FAILED, reason="network"),
    ])
    level, color = classify_summary(summary)
    assert level == "failure"
    assert color == 0xE74C3C


def test_zero_loaded_is_warning():
    summary = RunSummary(run_id="abc", source_results=[
        SourceResult("remoteok", SourceStatus.OK, jobs=[{"title": "x"}]),
    ])
    summary.loaded_count = 0
    level, color = classify_summary(summary)
    assert level == "warning"
    assert color == 0xF1C40F


def test_healthy_run_is_success():
    summary = RunSummary(run_id="abc", source_results=[
        SourceResult("remoteok", SourceStatus.OK, jobs=[{"title": "x"}]),
    ])
    summary.loaded_count = 1
    level, color = classify_summary(summary)
    assert level == "success"
    assert color == 0x2ECC71
