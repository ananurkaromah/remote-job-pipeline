"""Contract test: extractors must raise on failure, never swallow errors and
return an empty list to represent a failure state (ADR-003)."""
from unittest.mock import patch

import pytest

from rjp.exceptions import ExtractionError, FailureReason
from rjp.extract.experimental.glints import GlintsExtractor


def test_glints_disabled_by_default_raises():
    with patch("rjp.config.ENABLE_SELENIUM_SOURCES", False):
        with pytest.raises(ExtractionError) as exc_info:
            GlintsExtractor().extract()
        assert exc_info.value.reason == FailureReason.DISABLED
