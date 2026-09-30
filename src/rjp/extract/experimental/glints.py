"""Glints ID / Jobstreet Selenium scraper (ADR-022): OUT of the default pipeline.

Disabled unless ENABLE_SELENIUM_SOURCES=true. Requires Chrome/ChromeDriver
(INSTALL_CHROME=true at build time) and the optional Selenium dependency
group (requirements-optional.txt). Check the portal's terms of service
before enabling this in a scheduled run.
"""
from __future__ import annotations

from rjp import config
from rjp.exceptions import ExtractionError, FailureReason
from rjp.extract.base import BaseExtractor


class GlintsExtractor(BaseExtractor):
    name = "glints"

    def extract(self) -> list[dict]:
        if not config.ENABLE_SELENIUM_SOURCES:
            raise ExtractionError(self.name, FailureReason.DISABLED, "ENABLE_SELENIUM_SOURCES is false")

        # Intentionally not implemented in the default pipeline. If enabling
        # this source, implement it here using selenium (see
        # requirements-optional.txt) with explicit User-Agent rotation and
        # random delay via rjp.utils.http, and re-verify Glints' terms of
        # service first.
        raise ExtractionError(self.name, FailureReason.DISABLED, "not implemented; see module docstring")
