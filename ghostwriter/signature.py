"""Signatur am Briefende: einmalig und kanonisch aus den Einstellungen."""

from __future__ import annotations

import re

_GREETING_RE = re.compile(
    r"(mit\s+freundlichen\s+gr[uü]ßen|hochachtungsvoll|freundliche\s+gr[uü]ße)",
    re.IGNORECASE,
)
_SENDER_RE = re.compile(
    r"\b(dr\.?|med\.|facharzt|fachärztin|praxis|ärztin|arzt)\b",
    re.IGNORECASE,
)
_P_BLOCK_RE = re.compile(r"<p\b[^>]*>.*?</p>", re.IGNORECASE | re.DOTALL)


def _strip_tags(html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
    )
    return text


def _is_signature_paragraph(plain: str) -> bool:
    text = plain.strip()
    if not text or len(text) > 120:
        return False
    if _GREETING_RE.search(text):
        return True
    if _SENDER_RE.search(text):
        return True
    return False


def strip_trailing_signature(html: str) -> str:
    """Entfernt am Ende typische Gruß-/Absender-Absätze des LLM."""
    cleaned = html.strip()
    if not cleaned:
        return ""

    blocks = list(_P_BLOCK_RE.finditer(cleaned))
    if not blocks:
        return cleaned

    cut = len(cleaned)
    for match in reversed(blocks):
        between = cleaned[match.end() : cut]
        if between.strip():
            break
        plain = _strip_tags(match.group(0))
        if not _is_signature_paragraph(plain):
            break
        cut = match.start()

    return cleaned[:cut].rstrip()


def apply_signature(html: str, signature_html: str) -> str:
    """Hängt die Einstellungs-Signatur genau einmal an."""
    body = strip_trailing_signature(html)
    sig = signature_html.strip()
    if not sig:
        return body
    if not body:
        return sig
    return f"{body}\n{sig}"
