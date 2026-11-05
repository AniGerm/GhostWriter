"""Nachbearbeitung von LLM-Bericht-HTML."""

from __future__ import annotations

import re

_HEADING_RE = re.compile(
    r"(<(h[1-3])\b[^>]*>)(.*?)(</\2>)",
    re.IGNORECASE | re.DOTALL,
)
_BRACKET_WRAP_RE = re.compile(r"\[([^\[\]]+)\]")


def strip_heading_brackets(html: str) -> str:
    """Entfernt eckige Klammern um Stichwörter in Überschriften (h1–h3)."""

    def _clean(match: re.Match[str]) -> str:
        open_tag, _level, body, close_tag = match.groups()
        cleaned = _BRACKET_WRAP_RE.sub(r"\1", body)
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
        return f"{open_tag}{cleaned}{close_tag}"

    return _HEADING_RE.sub(_clean, html)
