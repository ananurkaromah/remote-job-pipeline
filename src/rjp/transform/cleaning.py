"""HTML stripping and text normalization."""
from __future__ import annotations

import html
import re

_TAG_RE = re.compile(r"<[^>]+>")
_MULTI_WS_RE = re.compile(r"[ \t\f\v]+")
_MULTI_NL_RE = re.compile(r"\n{3,}")


def strip_html(text: str) -> str:
    """Remove HTML tags and decode entities, keeping paragraph breaks readable."""
    if not text:
        return ""
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    text = re.sub(r"(?i)</li>", "\n", text)
    text = _TAG_RE.sub("", text)
    text = html.unescape(text)
    return text


def normalize_whitespace(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _MULTI_WS_RE.sub(" ", text)
    text = _MULTI_NL_RE.sub("\n\n", text)
    return text.strip()


def clean_description(raw_html: str) -> str:
    return normalize_whitespace(strip_html(raw_html))
