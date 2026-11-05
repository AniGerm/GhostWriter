"""Nachbearbeitung von LLM-Bericht-HTML."""

from __future__ import annotations

import re
from datetime import date

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


_INTRO_RE = re.compile(
    r'<h3 class="gw-reply-title"[^>]*>.*?</h3>\s*'
    r'(?:<p class="gw-reply-place"[^>]*>.*?</p>\s*)?'
    r'<p class="gw-reply-lead"[^>]*>.*?</p>\s*',
    re.IGNORECASE | re.DOTALL,
)
_ISO_DATE_RE = re.compile(r"\A(\d{4})-(\d{2})-(\d{2})\Z")


def _format_birth_date(value: str) -> str:
    match = _ISO_DATE_RE.match(value.strip())
    if not match:
        return value.strip()
    year, month, day = match.groups()
    return f"{day}.{month}.{year}"


_NAME_LABEL_RE = re.compile(
    r"(?:Patient(?:in)?|Name|Herrn|Frau)\s*[:\s]\s*"
    r"([A-ZÄÖÜ][a-zäöüß-]+(?:\s+[A-ZÄÖÜ][a-zäöüß-]+){0,2})"
)
_NAME_BORN_RE = re.compile(
    r"\b([A-ZÄÖÜ][a-zäöüß-]+(?:\s+[A-ZÄÖÜ][a-zäöüß-]+){1,2})\s*,?\s*(?:geboren|geb\.?)"
)
_BIRTH_RE = re.compile(
    r"(?:geboren|geb\.?)\s*(?:am\s*)?(\d{1,2})\.(\d{1,2})\.(\d{4})",
    re.IGNORECASE,
)
_HTML_ESC = str.maketrans({"<": "", ">": "", "&": "und"})


def _plain(value: str) -> str:
    return value.translate(_HTML_ESC).strip()


_TITLE_RE = re.compile(r"^(?:Herrn|Herr|Frau)\s+", re.IGNORECASE)


def _clean_name(value: str) -> str:
    return _TITLE_RE.sub("", value.strip().rstrip(",")).strip()


def extract_patient_identity(text: str) -> tuple[str, str]:
    """Liest Name und Geburtsdatum aus Anfrage oder Befund. Datum als ISO."""
    name = ""
    born_match = _NAME_BORN_RE.search(text)
    if born_match:
        name = _clean_name(born_match.group(1))
    if not name:
        label_match = _NAME_LABEL_RE.search(text)
        if label_match:
            name = _clean_name(label_match.group(1))
    birth = ""
    date_match = _BIRTH_RE.search(text)
    if date_match:
        day, month, year = date_match.groups()
        birth = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    return name, birth


def resolve_reply_identity(
    patient_label: str,
    birth_date: str,
    *sources: str,
) -> tuple[str, str]:
    """Name aus den Unterlagen, Datum daraus oder sonst vom Projektanfang."""
    found_name = ""
    found_birth = ""
    for source in sources:
        if not source.strip():
            continue
        name, born = extract_patient_identity(source)
        if name and not found_name:
            found_name = name
        if born and not found_birth:
            found_birth = born
    label = patient_label.strip()
    name = label or "die Patientin oder den Patienten"
    if found_name and (not label or len(found_name) > len(label)):
        name = found_name
    return name, found_birth or birth_date.strip()


def reply_intro_html(
    patient_label: str,
    birth_date: str,
    subjects: list[str] | None = None,
    *,
    place: str = "",
    issued_on: date | None = None,
) -> str:
    """Überschrift, rechts Ort und Datum, dann ein Satz zum GdB-Antrag."""
    del subjects
    name = _plain(patient_label) or "die Patientin oder den Patienten"
    born = _format_birth_date(birth_date)
    person = f"{name}, geb.: {born}" if born else name
    lead = (
        "Ärztliche Stellungnahme zum Antrag auf Feststellung eines Grades der Behinderung "
        f"für {person}."
    )
    when = issued_on or date.today()
    lines = [city for city in (_plain(place),) if city]
    lines.append(when.strftime("%d.%m.%Y"))
    title = (
        '<h3 class="gw-reply-title" style="font-size:14pt;font-weight:700;'
        'text-decoration:underline">Ärztlicher Befundbericht</h3>'
    )
    placed = (
        '<p class="gw-reply-place" style="text-align:right">' + "<br>".join(lines) + "</p>"
    )
    return f"{title}{placed}<p class=\"gw-reply-lead\">{lead}</p>"


def strip_reply_intro(html: str) -> str:
    """Entfernt eine zuvor eingesetzte Stellungnahme."""
    return _INTRO_RE.sub("", html).strip()


def ensure_reply_intro(
    html: str,
    patient_label: str,
    birth_date: str,
    *,
    letterhead_html: str = "",
    subjects: list[str] | None = None,
    place: str = "",
    issued_on: date | None = None,
) -> str:
    """Setzt Überschrift, Ort, Datum und den GdB-Satz hinter den Briefkopf."""
    cleaned = _INTRO_RE.sub("", html).strip()
    intro = reply_intro_html(
        patient_label,
        birth_date,
        subjects,
        place=place,
        issued_on=issued_on,
    )
    head = letterhead_html.strip()
    if head and cleaned.startswith(head):
        rest = cleaned[len(head) :].lstrip()
    elif head and head in cleaned:
        rest = cleaned.replace(head, "", 1).strip()
    else:
        rest = cleaned
    parts = [part for part in (head, intro, rest) if part]
    return "\n".join(parts)


def strip_heading_brackets(html: str) -> str:
    """Entfernt eckige Klammern um Stichwörter in Überschriften (h1-h3)."""

    def _clean(match: re.Match[str]) -> str:
        open_tag, _level, body, close_tag = match.groups()
        cleaned = _BRACKET_WRAP_RE.sub(r"\1", body)
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
        return f"{open_tag}{cleaned}{close_tag}"

    return _HEADING_RE.sub(_clean, html)


def _keep_ascii_ue(word: str) -> bool:
    """Französisch/Latein -uell und Quer/bequem bleiben mit ue."""
    low = word.lower()
    if "uell" in low:
        return True
    return low.startswith(("quer", "quelle", "bequem"))


def _restore_umlauts_in_text(text: str) -> str:
    if not text:
        return text

    def protect(match: re.Match[str]) -> str:
        word = match.group(0)
        if word in _UMLAUT_DENY:
            return word
        fixed = word
        if not _keep_ascii_ue(word):
            fixed = _UE_RE.sub("Ü", fixed)
            fixed = _ue_RE.sub("ü", fixed)
        fixed = _OE_RE.sub("Ö", fixed)
        fixed = _AE_RE.sub("Ä", fixed)
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
