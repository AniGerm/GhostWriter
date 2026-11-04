"""Update-Dialog: prüfen, laden, installieren."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ghostwriter import updates
from ghostwriter.ui import strings


class _UpdateWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, action: str) -> None:
        super().__init__()
        self._action = action

    def run(self) -> None:
        try:
            if self._action == "check":
                result = updates.check_for_update()
            elif self._action == "download":
                result = updates.download_update()
            elif self._action == "install":
                result = updates.install_update()
            else:
                raise ValueError(self._action)
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(type(exc).__name__)


class UpdateDialog(QDialog):
    """Zeigt Update-Status und Aktionen."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(strings.UPDATE_TITLE)
        self._threads: list[QThread] = []

        layout = QVBoxLayout(self)
        self._status = QLabel(strings.UPDATE_CHECKING)
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.hide()
        layout.addWidget(self._progress)

        row = QHBoxLayout()
        self._btn_check = QPushButton(strings.UPDATE_CHECK)
        self._btn_download = QPushButton(strings.UPDATE_DOWNLOAD)
        self._btn_install = QPushButton(strings.UPDATE_INSTALL)
        self._btn_download.setEnabled(False)
        self._btn_install.setEnabled(False)
        self._btn_check.clicked.connect(lambda: self._run("check"))
        self._btn_download.clicked.connect(lambda: self._run("download"))
        self._btn_install.clicked.connect(lambda: self._run("install"))
        row.addWidget(self._btn_check)
        row.addWidget(self._btn_download)
        row.addWidget(self._btn_install)
        layout.addLayout(row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        close = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close:
            close.clicked.connect(self.reject)
        layout.addWidget(buttons)

        self._apply_status(updates.get_status())

    def start_check(self) -> None:
        self._run("check")

    def _run(self, action: str) -> None:
        self._btn_check.setEnabled(False)
        self._btn_download.setEnabled(False)
        self._btn_install.setEnabled(False)
        if action == "download":
            self._progress.show()
            self._progress.setValue(0)
        thread = QThread(self)
        worker = _UpdateWorker(action)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        def on_finished(result: object) -> None:
            assert isinstance(result, dict)
            self._apply_status(result)
            thread.quit()

        def on_failed(name: str) -> None:
            self._status.setText(f"{strings.UPDATE_ERROR}: {name}")
            self._btn_check.setEnabled(True)
            thread.quit()

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        self._threads.append(thread)
        thread.start()

    def _apply_status(self, status: dict[str, Any]) -> None:
        phase = str(status.get("phase") or "idle")
        current = status.get("current_version") or updates.app_version()
        latest = status.get("latest_version")
        error = status.get("error")
        percent = int(status.get("download_percent") or 0)

        if phase == "checking":
            self._status.setText(strings.UPDATE_CHECKING)
        elif phase == "update-available":
            self._status.setText(
                strings.UPDATE_AVAILABLE.format(latest=latest, current=current)
            )
        elif phase == "up-to-date":
            self._status.setText(strings.UPDATE_UP_TO_DATE.format(current=current))
        elif phase == "downloading":
            self._progress.show()
            self._progress.setValue(percent)
            self._status.setText(strings.UPDATE_DOWNLOADING.format(percent=percent))
        elif phase == "downloaded":
            self._progress.setValue(100)
            self._status.setText(strings.UPDATE_DOWNLOADED)
        elif phase == "installing":
            self._status.setText(strings.UPDATE_INSTALLING)
        elif phase == "error":
            self._status.setText(f"{strings.UPDATE_ERROR}: {error or 'unbekannt'}")
        else:
            self._status.setText(strings.UPDATE_IDLE.format(current=current))

        self._btn_check.setEnabled(phase not in {"checking", "downloading", "installing"})
        self._btn_download.setEnabled(bool(status.get("available")) and phase in {
            "update-available",
            "error",
            "idle",
        })
        self._btn_install.setEnabled(phase == "downloaded")
