"""Dokumenttext: PDF-Textebene oder OCR-Fallback."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

# Mindestzahl alphanumerischer Zeichen gesamt, darunter gilt die Textebene als zu dünn.
MIN_ALNUM_CHARS = 20


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """Ergebnis der Textextraktion."""

    text: str
    page_count: int
    used_ocr: bool


def run_ocr(path: Path, work_dir: Path) -> ExtractionResult:
    """OCR-Einstieg (Subprozess). Wird in Unit-Tests per Monkeypatch ersetzt."""
    from ghostwriter.ocr.worker import ocr_file

    return ocr_file(path, work_dir)


def _text_layer(path: Path) -> tuple[str, int]:
    reader = PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts).strip(), len(reader.pages)


def _alnum_count(text: str) -> int:
    return sum(1 for ch in text if ch.isalnum())


def _is_thin(text: str, page_count: int) -> bool:
    if page_count <= 0:
        return True
    return _alnum_count(text) < MIN_ALNUM_CHARS


def extract_document_text(path: Path, *, ocr_work_dir: Path) -> ExtractionResult:
    """Extrahiert Text aus PDF/Bild; OCR nur wenn nötig.

    Args:
        path: Quelldatei (PDF oder Bild).
        ocr_work_dir: Arbeitsverzeichnis für OCR-Zwischenbilder.

    Returns:
        ExtractionResult mit Text, Seitenzahl und OCR-Flag.
    """
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        text, pages = _text_layer(path)
        if not _is_thin(text, pages):
            return ExtractionResult(text=text, page_count=pages, used_ocr=False)
        return run_ocr(path, ocr_work_dir)
    return run_ocr(path, ocr_work_dir)
