"""Dokumenttext: PDF-Textebene oder OCR-Fallback."""

from __future__ import annotations

import json
import subprocess
import sys
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
    """OCR im eigenen Prozess, damit GPU-Speicher danach wirklich frei wird."""
    work_dir.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [sys.executable, "-m", "ghostwriter.ocr.worker", str(path), str(work_dir)],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        if "MemoryError" in detail or "Out of memory" in detail:
            raise MemoryError(
                "Nicht genug Speicher für die Texterkennung. "
                "Bitte große Dateien seitenweise prüfen oder Ollama kurz entlasten."
            ) from None
        raise RuntimeError(detail or f"OCR-Prozess endete mit Code {proc.returncode}")
    payload = json.loads(proc.stdout)
    return ExtractionResult(
        text=str(payload.get("text", "")),
        page_count=int(payload.get("page_count", 0)),
        used_ocr=bool(payload.get("used_ocr", True)),
    )


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
