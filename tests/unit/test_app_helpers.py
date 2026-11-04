"""App helper coverage without full GUI event loop ownership."""

from __future__ import annotations

from pathlib import Path

import pytest
from ghostwriter.app import GhostWriterApp, _ensure_single_instance
from ghostwriter.inbox import list_new_spool_pdfs
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app  # type: ignore[return-value]


def test_single_instance_server(qapp: QApplication) -> None:
    server = _ensure_single_instance(qapp)
    assert server is not None
    server.close()
    from PySide6.QtNetwork import QLocalServer

    QLocalServer.removeServer("ghostwriter-local-instance")


def test_ghostwriter_app_scan_inbox(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    spool = tmp_path / "spool"
    spool.mkdir()
    pdf = spool / "job.pdf"
    pdf.write_bytes(b"%PDF")

    incoming: list[Path] = []

    class FakeWindow:
        def show(self) -> None:
            return None

        def showNormal(self) -> None:
            return None

        def raise_(self) -> None:
            return None

        def handle_incoming_file(self, path: Path) -> None:
            incoming.append(path)

    # Build app then replace window/spool
    from ghostwriter import app as app_mod

    monkeypatch.setattr(app_mod, "MainWindow", lambda **kwargs: FakeWindow())
    monkeypatch.setattr(app_mod, "default_data_root", lambda: tmp_path / "data")
    monkeypatch.setattr(app_mod, "default_spool_dir", lambda: spool)
    gw = GhostWriterApp(qapp)
    gw.spool_dir = spool
    gw.inbox_state = tmp_path / "state.json"
    gw.window = FakeWindow()  # type: ignore[assignment]
    gw._scan_inbox()
    assert incoming
    assert list_new_spool_pdfs(spool, state_path=gw.inbox_state) == []
