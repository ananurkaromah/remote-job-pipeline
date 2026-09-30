from datetime import datetime

import pytest

from rjp.utils.quota import QuotaSkip, RunBudget


def test_skips_on_non_scheduled_day():
    budget = RunBudget(max_requests_per_run=3, run_days=["MON"], quota_reserve=10)
    tuesday = datetime(2026, 9, 29)  # a Tuesday
    with pytest.raises(QuotaSkip):
        budget.check_scheduled_today(tuesday)


def test_allows_on_scheduled_day():
    budget = RunBudget(max_requests_per_run=3, run_days=["TUE"], quota_reserve=10)
    tuesday = datetime(2026, 9, 29)
    budget.check_scheduled_today(tuesday)  # should not raise


def test_stops_at_per_run_cap():
    budget = RunBudget(max_requests_per_run=2, run_days=[], quota_reserve=0)
    assert budget.can_make_request()
    budget.record_request()
    assert budget.can_make_request()
    budget.record_request()
    assert not budget.can_make_request()


def test_respects_remaining_quota_reserve():
    budget = RunBudget(max_requests_per_run=10, run_days=[], quota_reserve=5)
    budget.remaining_quota = 6
    assert budget.can_make_request()
    budget.remaining_quota = 5
    assert not budget.can_make_request()
