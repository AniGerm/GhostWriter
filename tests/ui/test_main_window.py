"""UI tests for MainWindow flows."""

from __future__ import annotations

from pathlib import Path

import pytest
from ghostwriter.settings import AppSettings
from ghostwriter.store import DocumentRole, ProjectStore
from ghostwriter.ui.main_window import MainWindow

pytestmark = pytest.mark.qt


@pytest.fixture()
def window(qtbot, tmp_path: Path) -> MainWindow:
    store = ProjectStore(tmp_path / "data")
    settings = AppSettings()
    win = MainWindow(
        store=store,
        settings=settings,
        settings_path=tmp_path / "settings.json",
        user_dict_path=tmp_path / "words.txt",
    )
    qtbot.addWidget(win)
    return win


def test_create_and_select_project(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ghostwriter.ui.main_window.QInputDialog.getText",
        lambda *a, **k: ("Patient X", True),
    )
    # First call patient, second reference - need side effect
    values = iter([("Patient X", True), ("AZ-9", True)])

    def fake_get_text(*_a: object, **_k: object) -> tuple[str, bool]:
        return next(values)

    monkeypatch.setattr("ghostwriter.ui.main_window.QInputDialog.getText", fake_get_text)
    window._new_project()
    assert window._store.list_projects()
    assert window._project_list.count() == 1


def test_save_notes_and_questions(window: MainWindow) -> None:
    project = window._store.create_project(patient_label="P", reference="R")
    window.refresh_projects()
    window._select_project(project.id)
    window._notes.setPlainText("Hinweis")
    window._questions.addItem("1. [Diabetes] Frage?")
    window._save_current()
    loaded = window._store.get_project(project.id)
    assert loaded is not None
    assert loaded.notes == "Hinweis"
    assert window._store.get_questions(project.id)[0].keyword == "Diabetes"


def test_handle_incoming_assigns_document(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf = tmp_path / "befund_neuro.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    class FakeDialog:
        DialogCode = type("C", (), {"Accepted": 1})

        def __init__(self, **kwargs: object) -> None:
            self._path = kwargs["source_path"]

        def exec(self) -> int:
            return 1

        def creates_new_project(self) -> bool:
            return True

        def patient_label(self) -> str:
            return "Neu"

        def reference(self) -> str:
            return "1"

        def existing_project_id(self) -> None:
            return None

        def selected_role(self) -> DocumentRole:
            return DocumentRole.BEFUND

        @property
        def source_path(self) -> Path:
            return self._path  # type: ignore[return-value]

    monkeypatch.setattr("ghostwriter.ui.main_window.ImportDialog", FakeDialog)

    started: list[str] = []

    def fake_extract(doc_id: str, path: Path, project_id: str) -> None:
        started.append(doc_id)
        window._store.update_document_text(doc_id, "text", 1)

    monkeypatch.setattr(window, "_start_extract", fake_extract)
    window.handle_incoming_file(pdf)
    assert started
    assert window._store.list_projects()
