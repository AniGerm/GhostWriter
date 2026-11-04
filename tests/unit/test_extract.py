"""Tests for PDF text-layer extraction heuristics."""

from __future__ import annotations

from pathlib import Path

import pytest
from ghostwriter.extract import ExtractionResult, extract_document_text


def _write_minimal_text_pdf(path: Path, visible: str) -> None:
    """Write a tiny PDF with a text operator (no reportlab needed)."""
    # Escape parentheses for PDF string.
    payload = visible.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 800 Td ({payload}) Tj ET"
    stream_bytes = stream.encode("latin-1", errors="replace")
    objects = [
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n",
        b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n",
        (
            b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n"
        ),
        (
            f"4 0 obj<< /Length {len(stream_bytes)} >>stream\n".encode()
            + stream_bytes
            + b"\nendstream\nendobj\n"
        ),
        b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(offsets)}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(
        (f"trailer<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n").encode()
    )
    path.write_bytes(bytes(out))


def _write_blank_pdf(path: Path) -> None:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    with path.open("wb") as fh:
        writer.write(fh)


def test_extracts_text_layer_without_ocr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf = tmp_path / "anfrage.pdf"
    _write_minimal_text_pdf(pdf, "Besteht Diabetes mellitus Typ 2?")

    def boom(*_a: object, **_k: object) -> ExtractionResult:
        raise AssertionError("OCR must not be called for text PDFs")

    monkeypatch.setattr("ghostwriter.extract.run_ocr", boom)
    result = extract_document_text(pdf, ocr_work_dir=tmp_path / "ocr")
    assert "Diabetes" in result.text
    assert result.used_ocr is False
    assert result.page_count >= 1


def test_falls_back_to_ocr_when_text_thin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf = tmp_path / "scan.pdf"
    _write_blank_pdf(pdf)

    def fake_ocr(path: Path, work_dir: Path) -> ExtractionResult:
        return ExtractionResult(
            text="OCR: Skoliose Grad II",
            page_count=1,
            used_ocr=True,
        )

    monkeypatch.setattr("ghostwriter.extract.run_ocr", fake_ocr)
    result = extract_document_text(pdf, ocr_work_dir=tmp_path / "ocr")
    assert result.used_ocr is True
    assert "Skoliose" in result.text
