"""Cache und Seitenzugriff für Druckvorschau-Bilder."""

from __future__ import annotations

from pathlib import Path

from ghostwriter.preview import ensure_preview_pages, page_preview_path
from PIL import Image


def test_ensure_preview_pages_caches_image(tmp_path: Path) -> None:
    src = tmp_path / "scan.png"
    Image.new("RGB", (40, 60), color=(240, 240, 240)).save(src)
    cache = tmp_path / "cache"
    first = ensure_preview_pages(src, cache)
    assert len(first) == 1
    assert first[0].is_file()
    second = ensure_preview_pages(src, cache)
    assert second == first


def test_page_preview_path_is_one_based(tmp_path: Path) -> None:
    src = tmp_path / "scan.png"
    Image.new("RGB", (40, 60), color=(200, 200, 200)).save(src)
    cache = tmp_path / "cache"
    assert page_preview_path(src, cache, 0) is None
    assert page_preview_path(src, cache, 1) is not None
    assert page_preview_path(src, cache, 2) is None
