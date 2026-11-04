"""PDF/image rendering for OCR."""

from __future__ import annotations

from pathlib import Path

from ghostwriter.ocr.pdf_render import render_pages
from PIL import Image


def test_render_image(tmp_path: Path) -> None:
    src = tmp_path / "page.png"
    Image.new("RGB", (100, 80), color=(255, 255, 255)).save(src)
    outs = render_pages(src, tmp_path / "out")
    assert len(outs) == 1
    assert outs[0].is_file()


def test_render_pdf(tmp_path: Path) -> None:
    from pypdf import PdfWriter

    pdf = tmp_path / "x.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with pdf.open("wb") as fh:
        writer.write(fh)
    outs = render_pages(pdf, tmp_path / "pages", dpi=72)
    assert len(outs) == 1


def test_unsupported(tmp_path: Path) -> None:
    bad = tmp_path / "x.txt"
    bad.write_text("x")
    import pytest

    with pytest.raises(ValueError):
        render_pages(bad, tmp_path / "o")
