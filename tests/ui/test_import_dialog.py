"""UI tests for ImportDialog."""

from __future__ import annotations

from pathlib import Path

import pytest
from ghostwriter.store import DocumentRole, Project
from ghostwriter.ui.import_dialog import ImportDialog

pytestmark = pytest.mark.qt


def test_import_dialog_defaults_to_new_project(qtbot, tmp_path: Path) -> None:
    pdf = tmp_path / "anfrage.pdf"
    pdf.write_bytes(b"%PDF")
    projects = [Project(id="abc", patient_label="Alt", reference="1", created_at="", updated_at="")]
    dialog = ImportDialog(
        source_path=pdf,
        projects=projects,
        suggested_role=DocumentRole.ANFRAGE,
    )
    qtbot.addWidget(dialog)
    assert dialog.creates_new_project() is True
    assert dialog.selected_role() is DocumentRole.ANFRAGE
    dialog._patient.setText("Neu")
    dialog._existing.setChecked(True)
    assert dialog.creates_new_project() is False
    assert dialog.existing_project_id() == "abc"
