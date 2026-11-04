"""Seitenbilder für die Druckvorschau (A4-Darstellung der Anhänge)."""

from __future__ import annotations

from pathlib import Path

from ghostwriter.ocr.pdf_render import render_pages

PREVIEW_DPI = 110


def preview_cache_dir(data_root: Path, document_id: str) -> Path:
    """Cache-Verzeichnis für gerenderte Vorschauseiten eines Dokuments."""
    return data_root / "preview" / document_id


def ensure_preview_pages(
    source: Path,
    cache_dir: Path,
    *,
    dpi: int = PREVIEW_DPI,
) -> list[Path]:
    """Rendert Dokumentseiten als PNG und cached sie unter cache_dir.

    Bereits vorhandene PNGs werden wiederverwendet, wenn die Quelle nicht
    neuer ist als die Cache-Dateien.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(cache_dir.glob("*.png"))
    if existing and source.is_file():
        source_mtime = source.stat().st_mtime
        if all(p.stat().st_mtime >= source_mtime for p in existing):
            return existing
    for old in existing:
        old.unlink(missing_ok=True)
    return render_pages(source, cache_dir, dpi=dpi)


def page_preview_path(
    source: Path,
    cache_dir: Path,
    page_number: int,
    *,
    dpi: int = PREVIEW_DPI,
) -> Path | None:
    """Pfad zur PNG-Seite (1-basiert) oder None, wenn die Seite fehlt."""
    if page_number < 1:
        return None
    pages = ensure_preview_pages(source, cache_dir, dpi=dpi)
    index = page_number - 1
    if index >= len(pages):
        return None
    return pages[index]
