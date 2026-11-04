"""OCR worker with mocked engine."""

from __future__ import annotations

from pathlib import Path

import pytest
from ghostwriter.ocr import worker as worker_mod
from PIL import Image


def test_ocr_file_uses_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    src = tmp_path / "p.png"
    Image.new("RGB", (40, 40), color=(255, 255, 255)).save(src)

    monkeypatch.setattr(worker_mod, "render_pages", lambda path, dest: [src])

    import ghostwriter.ocr.engine as engine

    monkeypatch.setattr(engine, "ocr_image", lambda p: "OCR Text")
    monkeypatch.setattr(engine, "clear_pipeline", lambda: None)

    # Patch imports inside ocr_file
    monkeypatch.setattr("ghostwriter.ocr.engine.ocr_image", lambda p: "OCR Text")
    monkeypatch.setattr("ghostwriter.ocr.engine.clear_pipeline", lambda: None)

    result = worker_mod.ocr_file(src, tmp_path / "work")
    assert result.used_ocr is True
    assert "OCR Text" in result.text
    assert result.page_count == 1


def test_worker_main(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    src = tmp_path / "p.png"
    Image.new("RGB", (10, 10)).save(src)
    monkeypatch.setattr(
        worker_mod,
        "ocr_file",
        lambda path, work: type("R", (), {"text": "t", "page_count": 1, "used_ocr": True})(),
    )
    assert worker_mod.main([str(src), str(tmp_path / "w")]) == 0
    assert "page_count" in capsys.readouterr().out
    assert worker_mod.main([]) == 2
