"""Nachbearbeitung von LLM-Bericht-HTML."""

from __future__ import annotations

import re

_HEADING_RE = re.compile(
    r"(<(h[1-3])\b[^>]*>)(.*?)(</\2>)",
    re.IGNORECASE | re.DOTALL,
)
_BRACKET_WRAP_RE = re.compile(r"\[([^\[\]]+)\]")
_TAG_OR_TEXT_RE = re.compile(r"(<[^>]+>)|([^<]+)")

# ASCII-Umlaut-Digraphen nur nach Konsonant/Wortanfang, nicht nach Vokal
# (verhindert Feuer/Dauer/neuer → Feür/Daür/neür).
_AE_RE = re.compile(r"(?<![aeiouäöüAEIOUÄÖÜ])Ae")
_OE_RE = re.compile(r"(?<![aeiouäöüAEIOUÄÖÜ])Oe")
_UE_RE = re.compile(r"(?<![aeiouäöüAEIOUÄÖÜ])Ue")
_ae_RE = re.compile(r"(?<![aeiouäöüAEIOUÄÖÜ])ae")
_oe_RE = re.compile(r"(?<![aeiouäöüAEIOUÄÖÜ])oe")
_ue_RE = re.compile(r"(?<![aeiouäöüAEIOUÄÖÜ])ue")

# Seltene False-Positives trotz Konsonant-Regel
_UMLAUT_DENY = {
    "Statuen",
    "statuen",
    "Individuen",
    "individuen",
}


_ZU_FRAGE_RE = re.compile(
    r"^\s*(?:zu\s+)?frage\s+\d+\s*[:.\-]*\s*",
    re.IGNORECASE,
)
_BLOCK_RE = re.compile(
    r"(<(h[1-3]|p)\b[^>]*>)(.*?)(</\2>)",
    re.IGNORECASE | re.DOTALL,
)


def rewrite_frage_labels(html: str) -> str:
    """Entfernt 'Zu Frage N' aus Überschriften und Absatzanfängen.

    Überschriften behalten den Resttitel (z. B. 'Hilfsmittel').
    Bleibt nur das Frage-Label übrig, fällt die Überschrift weg.
    """

    def _clean(match: re.Match[str]) -> str:
        open_tag, _level, body, close_tag = match.groups()
        text = re.sub(r"<[^>]+>", "", body)
        stripped = _ZU_FRAGE_RE.sub("", text).strip()
        if not stripped:
            return ""
        if stripped == text.strip():
            return match.group(0)
        return f"{open_tag}{stripped}{close_tag}"

    return _BLOCK_RE.sub(_clean, html)


def strip_heading_brackets(html: str) -> str:
    """Entfernt eckige Klammern um Stichwörter in Überschriften (h1-h3)."""

    def _clean(match: re.Match[str]) -> str:
        open_tag, _level, body, close_tag = match.groups()
        cleaned = _BRACKET_WRAP_RE.sub(r"\1", body)
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
        return f"{open_tag}{cleaned}{close_tag}"

    return _HEADING_RE.sub(_clean, html)


def _restore_umlauts_in_text(text: str) -> str:
    if not text:
        return text

    def protect(match: re.Match[str]) -> str:
        word = match.group(0)
        if word in _UMLAUT_DENY:
            return word
        fixed = word
        fixed = _UE_RE.sub("Ü", fixed)
        fixed = _OE_RE.sub("Ö", fixed)
        fixed = _AE_RE.sub("Ä", fixed)
        fixed = _ue_RE.sub("ü", fixed)
        fixed = _oe_RE.sub("ö", fixed)
        fixed = _ae_RE.sub("ä", fixed)
        return fixed

    return re.sub(r"[A-Za-zÄÖÜäöüß]+", protect, text)


def restore_ascii_umlauts(html: str) -> str:
    """Ersetzt ae/oe/ue in Textknoten durch ä/ö/ü (LLM-ASCII → Deutsch)."""

    def _part(match: re.Match[str]) -> str:
        tag, text = match.group(1), match.group(2)
        if tag is not None:
            return tag
        return _restore_umlauts_in_text(text or "")

    return _TAG_OR_TEXT_RE.sub(_part, html)
