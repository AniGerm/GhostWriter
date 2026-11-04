"""PDF-/Bild-Rendering für OCR."""

from __future__ import annotations

from pathlib import Path

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}


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
        scale = dpi / 72
        for index in range(len(pdf)):
            page = pdf[index]
            try:
                bitmap = page.render(scale=scale)
                image = bitmap.to_pil().convert("RGB")
                out = dest_dir / f"{index + 1:04d}.png"
                image.save(out, "PNG")
                outs.append(out)
            finally:
                page.close()
    finally:
        pdf.close()
    return outs


def _copy_image(src: Path, dest: Path) -> Path:
    from PIL import Image

    image = Image.open(src).convert("RGB")
    image.save(dest, "PNG")
    return dest
