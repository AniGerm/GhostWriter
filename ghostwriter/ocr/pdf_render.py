"""PDF-/Bild-Rendering für OCR."""

from __future__ import annotations

from pathlib import Path
from typing import Any

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}


def count_pages(source: Path) -> int:
    """Seitenzahl, ohne die Seiten zu rastern."""
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
    bitmap = page.render(scale=scale, rev_byteorder=True)
    image = bitmap.to_pil().convert("RGB")
    if (shown_w > shown_h) != (image.width > image.height):
        image = page.render(
            scale=scale,
            rotation=page.get_rotation(),
            rev_byteorder=True,
        ).to_pil().convert("RGB")
    image.save(dest, "PNG")


def _copy_image(src: Path, dest: Path) -> Path:
    from PIL import Image

    image = Image.open(src).convert("RGB")
    image.save(dest, "PNG")
    return dest
