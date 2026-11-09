"""OCR worker with mocked engine."""

from __future__ import annotations

from pathlib import Path

import pytest
from ghostwriter.ocr import worker as worker_mod
from PIL import Image


def test_ocr_file_uses_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    src = tmp_path / "p.png"
    Image.new("RGB", (40, 40), color=(255, 255, 255)).save(src)

    monkeypatch.setattr(worker_mod, "count_pages", lambda path: 1)

    def fake_render(path: Path, dest: Path, page_number: int, *, dpi: int = 150) -> Path:
        Image.new("RGB", (20, 20), color=(255, 255, 255)).save(dest)
        return dest

    monkeypatch.setattr(worker_mod, "render_one_page", fake_render)
    monkeypatch.setattr("ghostwriter.ocr.engine.ocr_image", lambda p: "OCR Text")
    monkeypatch.setattr("ghostwriter.ocr.engine.clear_pipeline", lambda: None)

    result = worker_mod.ocr_file(src, tmp_path / "work")
    assert result.used_ocr is True
    assert "OCR Text" in result.text
    assert result.page_count == 1
    assert not any((tmp_path / "work" / "pages").glob("*.png"))


def test_ocr_file_processes_pages_one_by_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    src = tmp_path / "multi.pdf"
    src.write_bytes(b"%PDF")
    seen: list[int] = []
    live_pngs: list[int] = []

    monkeypatch.setattr(worker_mod, "count_pages", lambda path: 3)

    def fake_render(path: Path, dest: Path, page_number: int, *, dpi: int = 150) -> Path:
        seen.append(page_number)
        dest.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (12, 12)).save(dest)
        live_pngs.append(len(list(dest.parent.glob("*.png"))))
        return dest

    monkeypatch.setattr(worker_mod, "render_one_page", fake_render)
    monkeypatch.setattr("ghostwriter.ocr.engine.ocr_image", lambda p: f"Seite {p.stem}")
    monkeypatch.setattr("ghostwriter.ocr.engine.clear_pipeline", lambda: None)

    result = worker_mod.ocr_file(src, tmp_path / "work")
    assert seen == [1, 2, 3]
    assert live_pngs == [1, 1, 1]
    assert result.page_count == 3
    assert "Seite 0001" in result.text


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
