"""Exercise editor toolbar actions for coverage."""

from __future__ import annotations

from pathlib import Path

import pytest
from ghostwriter.ui.editor import ReportEditor
from PySide6.QtCore import Qt

pytestmark = pytest.mark.qt


def test_formatting_actions(qtbot, tmp_path: Path) -> None:
    editor = ReportEditor(user_dict_path=tmp_path / "w.txt")
    qtbot.addWidget(editor)
    editor.set_html("<p>Wort</p>")
    editor._bold()
    editor._italic()
    editor._underline()
    editor._align(Qt.AlignmentFlag.AlignJustify)
    editor._bullet()
    editor._apply_font_family("Liberation Serif")
    editor._apply_font_size(14)
    editor._apply_line_spacing(150)
    out = tmp_path / "x.odt"
    editor.export_odt(out)
    assert out.is_file()
