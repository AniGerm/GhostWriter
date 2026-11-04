"""MainWindow generate/print paths with fakes."""

from __future__ import annotations

from pathlib import Path

import pytest
from ghostwriter.extract import ExtractionResult
from ghostwriter.settings import AppSettings
from ghostwriter.store import DocumentRole, ProjectStore, Question
from ghostwriter.ui.main_window import MainWindow

pytestmark = pytest.mark.qt


@pytest.fixture()
def window(qtbot, tmp_path: Path) -> MainWindow:
    store = ProjectStore(tmp_path / "data")
    win = MainWindow(
        store=store,
        settings=AppSettings(),
        settings_path=tmp_path / "settings.json",
        user_dict_path=tmp_path / "words.txt",
    )
    qtbot.addWidget(win)
    return win


def test_generate_requires_anfrage(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    messages: list[str] = []
    monkeypatch.setattr(
        "ghostwriter.ui.main_window.QMessageBox.information",
        lambda *a, **k: messages.append("info"),
    )
    project = window._store.create_project(patient_label="P", reference="")
    window.refresh_projects()
    window._select_project(project.id)
    window._generate()
    assert messages


def test_generate_runs_worker(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = window._store.create_project(patient_label="P", reference="")
    src = tmp_path / "a.pdf"
    src.write_bytes(b"%PDF")
    doc = window._store.add_document(project.id, src, DocumentRole.ANFRAGE, "a.pdf")
    window._store.update_document_text(doc.id, "Frage Diabetes?", 1)
    window.refresh_projects()
    window._select_project(project.id)

    class _Signal:
        def __init__(self) -> None:
            self._slots: list = []

        def connect(self, slot) -> None:  # type: ignore[no-untyped-def]
            self._slots.append(slot)

        def emit(self, *args: object) -> None:
            for s in self._slots:
                s(*args)

    class FakeThread:
        def __init__(self, *a: object, **k: object) -> None:
            self.started = _Signal()
            self.finished = _Signal()

        def start(self) -> None:
            self.started.emit()

        def quit(self) -> None:
            self.finished.emit()

    class FakeWorker:
        def __init__(self, **kwargs: object) -> None:
            self.finished = _Signal()
            self.questions_ready = _Signal()
            self.failed = _Signal()

        def moveToThread(self, *_a: object) -> None:
            return None

        def run(self) -> None:
            self.questions_ready.emit([Question(1, "Diabetes?", "Diabetes")])
            self.finished.emit("<p>Antwort</p>")

        def deleteLater(self) -> None:
            return None

    monkeypatch.setattr("ghostwriter.ui.main_window.QThread", FakeThread)
    monkeypatch.setattr("ghostwriter.ui.main_window.GenerateWorker", FakeWorker)
    window._generate()
    assert "Antwort" in window._editor.to_html()


def test_start_extract(window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = window._store.create_project(patient_label="P", reference="")
    src = tmp_path / "b.pdf"
    src.write_bytes(b"%PDF")
    doc = window._store.add_document(project.id, src, DocumentRole.BEFUND, "b.pdf")

    class _Signal:
        def __init__(self) -> None:
            self._slots: list = []

        def connect(self, slot) -> None:  # type: ignore[no-untyped-def]
            self._slots.append(slot)

        def emit(self, *a: object) -> None:
            for s in self._slots:
                s(*a)

    class FakeThread:
        def __init__(self, *a: object, **k: object) -> None:
            self.started = _Signal()
            self.finished = _Signal()

        def start(self) -> None:
            self.started.emit()

        def quit(self) -> None:
            self.finished.emit()

    class FakeWorker:
        def __init__(self, *a: object, **k: object) -> None:
            self.finished = _Signal()
            self.failed = _Signal()

        def moveToThread(self, *_a: object) -> None:
            return None

        def run(self) -> None:
            self.finished.emit(ExtractionResult("text", 2, False))

        def deleteLater(self) -> None:
            return None

    monkeypatch.setattr("ghostwriter.ui.main_window.QThread", FakeThread)
    monkeypatch.setattr("ghostwriter.ui.main_window.ExtractWorker", FakeWorker)
    window._start_extract(doc.id, Path(doc.stored_path), project.id)
    updated = window._store.list_documents(project.id)[0]
    assert updated.extracted_text == "text"
