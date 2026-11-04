"""Update dialog UI test."""

from __future__ import annotations

import pytest
from ghostwriter.ui.update_dialog import UpdateDialog

pytestmark = pytest.mark.qt


def test_update_dialog_shows_available(qtbot, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ghostwriter.ui.update_dialog.updates.get_status",
        lambda: {
            "phase": "update-available",
            "available": True,
            "current_version": "0.1.0",
            "latest_version": "0.2.0",
            "download_percent": 0,
            "error": None,
        },
    )
    dialog = UpdateDialog()
    qtbot.addWidget(dialog)
    assert dialog._btn_download.isEnabled()
    assert "0.2.0" in dialog._status.text()
