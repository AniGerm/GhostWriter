"""Worker unit tests with fakes (no real OCR/Ollama)."""

from __future__ import annotations

from pathlib import Path

import pytest
from ghostwriter.extract import ExtractionResult
from ghostwriter.settings import AppSettings
from ghostwriter.store import Question
from ghostwriter.ui.workers import ExtractWorker, GenerateWorker
from PySide6.QtCore import QCoreApplication


@pytest.fixture(scope="module")
def qapp() -> QCoreApplication:
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


def test_extract_worker_success(
    qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "ghostwriter.ui.workers.extract_document_text",
        lambda path, ocr_work_dir: ExtractionResult("ok", 1, False),
    )
    worker = ExtractWorker(tmp_path / "x.pdf", tmp_path / "w")
    results: list[object] = []
    worker.finished.connect(results.append)
    worker.run()
    assert results and isinstance(results[0], ExtractionResult)


def test_extract_worker_failure(
    qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_a: object, **_k: object) -> ExtractionResult:
        raise RuntimeError("x")

    monkeypatch.setattr("ghostwriter.ui.workers.extract_document_text", boom)
    worker = ExtractWorker(tmp_path / "x.pdf", tmp_path / "w")
    errors: list[str] = []
    worker.failed.connect(errors.append)
    worker.run()
    assert errors == ["RuntimeError"]


def test_generate_worker(qapp: QCoreApplication, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            pass

        def chat_json(self, **kwargs: object) -> dict[str, object]:
            return {"html": "<p>x</p>"}

    class FakePipe:
        def __init__(self, client: object) -> None:
            pass

        def extract_questions(self, text: str) -> list[Question]:
            return [Question(1, "Q?", "K")]

        def summarize_finding(self, text: str, display_name: str = "") -> object:
            return type("S", (), {"summary": "sum", "source": display_name})()

        def compose_report(self, **kwargs: object) -> str:
            return "<p>done</p>"

    monkeypatch.setattr("ghostwriter.ui.workers.OllamaClient", FakeClient)
    monkeypatch.setattr("ghostwriter.ui.workers.ReportPipeline", FakePipe)
    worker = GenerateWorker(
        settings=AppSettings(),
        anfrage_text="Fragen",
        findings=[("a.pdf", "befund")],
        notes="n",
        questions=None,
    )
    htmls: list[str] = []
    qs: list[object] = []
    worker.finished.connect(htmls.append)
    worker.questions_ready.connect(qs.append)
    worker.run()
    assert htmls == ["<p>done</p>"]
    assert qs
