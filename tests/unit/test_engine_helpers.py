"""OCR engine helpers without loading Paddle."""

from __future__ import annotations

from ghostwriter.ocr.engine import _texts_from_result, clear_pipeline


def test_texts_from_dict() -> None:
    assert _texts_from_result({"rec_texts": ["Hallo", "Welt"]}) == ["Hallo", "Welt"]
    assert _texts_from_result({"text": "x"}) == ["x"]
    assert _texts_from_result(None) == []


def test_clear_pipeline_noop() -> None:
    clear_pipeline()
