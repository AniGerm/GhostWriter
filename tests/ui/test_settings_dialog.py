"""Settings dialog UI test."""

from __future__ import annotations

import pytest
from ghostwriter.settings import AppSettings
from ghostwriter.ui.settings_dialog import SettingsDialog

pytestmark = pytest.mark.qt


def test_settings_dialog_roundtrip(qtbot) -> None:
    settings = AppSettings(flat_fee=27.5, ollama_model="test:model")
    dialog = SettingsDialog(settings)
    qtbot.addWidget(dialog)
    dialog._flat.setValue(40.0)
    dialog._model.setText("other:model")
    result = dialog.result_settings()
    assert result.flat_fee == pytest.approx(40.0)
    assert result.ollama_model == "other:model"
