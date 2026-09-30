"""Extractor contract (ADR-003): raise on failure, never swallow errors.

An empty list from `extract()` means "healthy source, no matching data".
Any failure -- network, auth, quota, or a changed response shape -- must be
raised as ExtractionError (or PartialExtractionError if some jobs were
already collected). See docs/architecture.md section 3.2.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class BaseExtractor(ABC):
    name: str

    @abstractmethod
    def extract(self) -> list[dict]:
        """Return raw job dicts. Raise ExtractionError/PartialExtractionError on failure."""
        raise NotImplementedError
