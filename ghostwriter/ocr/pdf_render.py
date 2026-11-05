"""PDF-/Bild-Rendering für OCR.

PDFium verträgt keine parallelen Aufrufe. Seitenzahl und Seitenbild laufen
deshalb hinter derselben Sperre, sonst stürzt der Prozess ab.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}
_pdfium_lock = threading.Lock()


def count_pages(source: Path) -> int:
    """Seitenzahl, ohne die Seiten zu rastern."""
    with _pdfium_lock:
        return _count_pages(source)


def _count_pages(source: Path) -> int:
    suffix = source.suffix.lower()
    if suffix in IMAGE_EXTS:
        return 1
    if suffix != ".pdf":
        raise ValueError(f"Nicht unterstütztes Format: {suffix}")
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(source))
    try:
        return len(pdf)
    finally:
        pdf.close()


def render_one_page(source: Path, dest: Path, page_number: int, *, dpi: int = 200) -> Path | None:
    """Rendert genau eine 1-basierte Seite nach dest. None, wenn sie fehlt."""
    with _pdfium_lock:
        return _render_one_page(source, dest, page_number, dpi=dpi)


def _render_one_page(source: Path, dest: Path, page_number: int, *, dpi: int) -> Path | None:
    if page_number < 1:
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix.lower()
    if suffix in IMAGE_EXTS:
        if page_number != 1:
            return None
        return _copy_image(source, dest)
    if suffix != ".pdf":
        raise ValueError(f"Nicht unterstütztes Format: {suffix}")
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(source))
    try:
        index = page_number - 1
        if index >= len(pdf):
            return None
        page = pdf[index]
        try:
            _write_page_png(page, dest, dpi=dpi)
        finally:
            page.close()
    finally:
        pdf.close()
    return dest


def render_pages(source: Path, dest_dir: Path, *, dpi: int = 200) -> list[Path]:
    """Rendert PDF-Seiten oder kopiert ein Bild nach dest_dir als PNG-Liste."""
    with _pdfium_lock:
        return _render_pages(source, dest_dir, dpi=dpi)


def _render_pages(source: Path, dest_dir: Path, *, dpi: int) -> list[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix.lower()
    if suffix == ".pdf":
        return _render_pdf(source, dest_dir, dpi=dpi)
    if suffix in IMAGE_EXTS:
        return [_copy_image(source, dest_dir / "0001.png")]
    raise ValueError(f"Nicht unterstütztes Format: {suffix}")


def _render_pdf(pdf_path: Path, dest_dir: Path, *, dpi: int) -> list[Path]:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(pdf_path))
    outs: list[Path] = []
    try:
        for index in range(len(pdf)):
            page = pdf[index]
            try:
                out = dest_dir / f"{index + 1:04d}.png"
                _write_page_png(page, out, dpi=dpi)
                outs.append(out)
            finally:
                page.close()
    finally:
        pdf.close()
    return outs


def _write_page_png(page: Any, dest: Path, *, dpi: int) -> None:
    """Schreibt eine pdfium-Seite als PNG. Dreht nur, wenn die Bitmap quer zur Seite liegt."""
    shown_w, shown_h = page.get_size()
    scale = dpi / 72
    image = _page_image(page, scale=scale, rotation=None)
    if (shown_w > shown_h) != (image.width > image.height):
        image = _page_image(page, scale=scale, rotation=page.get_rotation())
    image.save(dest, "PNG")


def _page_image(page: Any, *, scale: float, rotation: int | None) -> Any:
    """Kopiert die Bitmap, bevor PDFium den Puffer wieder freigibt."""
    kwargs: dict[str, Any] = {"scale": scale, "rev_byteorder": True}
    if rotation is not None:
        kwargs["rotation"] = rotation
    bitmap = page.render(**kwargs)
    try:
        return bitmap.to_pil().convert("RGB").copy()
    finally:
        bitmap.close()


def _copy_image(src: Path, dest: Path) -> Path:
    from PIL import Image

    image = Image.open(src).convert("RGB")
    image.save(dest, "PNG")
    return dest
