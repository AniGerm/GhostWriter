"""Seitenbilder für die Druckvorschau (A4-Darstellung der Anhänge)."""

from __future__ import annotations

import threading
from pathlib import Path

from ghostwriter.ocr.pdf_render import count_pages, render_one_page, render_pages

PREVIEW_DPI = 96

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def preview_cache_dir(data_root: Path, document_id: str) -> Path:
    """Cache-Verzeichnis für gerenderte Vorschauseiten eines Dokuments."""
    return data_root / "preview" / document_id


def _page_lock(dest: Path) -> threading.Lock:
    key = str(dest)
    with _locks_guard:
        lock = _locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _locks[key] = lock
        return lock


def _cache_is_fresh(source: Path, dest: Path) -> bool:
    if not dest.is_file() or not source.is_file():
        return False
    return dest.stat().st_mtime >= source.stat().st_mtime


def ensure_preview_pages(
    source: Path,
    cache_dir: Path,
    *,
    dpi: int = PREVIEW_DPI,
) -> list[Path]:
    """Rendert alle Dokumentseiten als PNG und cached sie unter cache_dir."""
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
    """PNG einer einzelnen Seite. Andere Seiten werden nicht gerastert."""
    if page_number < 1:
        return None
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / f"{page_number:04d}.png"
    if _cache_is_fresh(source, dest):
        return dest
    with _page_lock(dest):
        if _cache_is_fresh(source, dest):
            return dest
        return render_one_page(source, dest, page_number, dpi=dpi)


def document_page_count(source: Path) -> int:
    """Seitenzahl ohne Rasterung."""
    return count_pages(source)
