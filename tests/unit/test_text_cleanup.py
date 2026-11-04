"""Tests for German OCR cleanup."""

from __future__ import annotations

from ghostwriter.ocr.text_cleanup import cleanup_german_ocr


def test_splits_merged_camel_case() -> None:
    assert "Hallo Welt" in cleanup_german_ocr("HalloWelt")


def test_normalizes_guillemets() -> None:
    cleaned = cleanup_german_ocr("<<Test>>")
    assert cleaned.startswith("«")
    assert cleaned.endswith("»")
    assert "Test" in cleaned


def test_empty() -> None:
    assert cleanup_german_ocr("   ") == ""
