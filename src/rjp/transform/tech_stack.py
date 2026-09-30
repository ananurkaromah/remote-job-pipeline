"""Tech stack extraction using the alias dictionary in resources/tech_aliases.yaml."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml

_RESOURCES = Path(__file__).resolve().parent.parent / "resources"


@lru_cache(maxsize=1)
def _aliases() -> dict[str, list[str]]:
    with open(_RESOURCES / "tech_aliases.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def extract_tech_stack(text: str) -> list[str]:
    """Return canonical tech names found in `text`, preserving dictionary order."""
    if not text:
        return []
    lower = f" {text.lower()} "
    found: list[str] = []
    for canonical, aliases in _aliases().items():
        for alias in aliases:
            pattern = r"(?<![\w+#.-])" + re.escape(alias.lower()) + r"(?![\w+#-])"
            if re.search(pattern, lower):
                found.append(canonical)
                break
    return found
