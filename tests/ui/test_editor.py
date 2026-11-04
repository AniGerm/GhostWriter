"""UI tests for ReportEditor."""

from __future__ import annotations

from pathlib import Path

import pytest
from ghostwriter.ui.editor import ReportEditor

pytestmark = pytest.mark.qt


def test_set_and_get_html(qtbot, tmp_path: Path) -> None:
    editor = ReportEditor(user_dict_path=tmp_path / "words.txt")
    qtbot.addWidget(editor)
    editor.set_html("<p>Hallo Diabetes</p>")
    assert "Diabetes" in editor.to_html()
    assert editor.page_count_estimate() >= 1


def test_export_pdf(qtbot, tmp_path: Path) -> None:
    editor = ReportEditor(user_dict_path=tmp_path / "words.txt")
    qtbot.addWidget(editor)
    editor.set_html("<p>Exporttest</p>")
    out = tmp_path / "out.pdf"
    editor.export_pdf(out)
    assert out.is_file()
    assert out.stat().st_size > 0
