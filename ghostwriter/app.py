"""GhostWriter Einstieg: Tray, Einzelinstanz, Inbox-Überwachung."""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, QObject, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from ghostwriter.inbox import list_new_spool_pdfs, mark_processed
from ghostwriter.paths import default_data_root, default_spool_dir
from ghostwriter.settings import load_settings, save_settings
from ghostwriter.store import ProjectStore
from ghostwriter.ui import strings
from ghostwriter.ui.main_window import MainWindow
from ghostwriter.ui.update_dialog import UpdateDialog
from ghostwriter.updates import check_for_update, set_github_repo


class _StartupUpdateCheck(QObject):
    finished = Signal(object)

    def run(self) -> None:
        self.finished.emit(check_for_update())


INSTANCE_KEY = "ghostwriter-local-instance"


def _ensure_single_instance(app: QApplication) -> QLocalServer | None:
    socket = QLocalSocket()
    socket.connectToServer(INSTANCE_KEY)
    if socket.waitForConnected(200):
        socket.write(b"raise")
        socket.flush()
        socket.waitForBytesWritten(200)
        return None
    QLocalServer.removeServer(INSTANCE_KEY)
    server = QLocalServer(app)
    server.listen(INSTANCE_KEY)
    return server


class GhostWriterApp:
    """Orchestriert Hauptfenster, Tray und Spool-Inbox."""

    def __init__(self, app: QApplication) -> None:
        self.app = app
        self.data_root = default_data_root()
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.settings_path = self.data_root / "settings.json"
        self.settings = load_settings(self.settings_path)
        if not self.settings_path.is_file():
            save_settings(self.settings_path, self.settings)
        self.store = ProjectStore(self.data_root)
        self.spool_dir = (
            Path(self.settings.spool_dir) if self.settings.spool_dir else default_spool_dir()
        )
        self.inbox_state = self.data_root / "inbox_state.json"
        self.window = MainWindow(
            store=self.store,
            settings=self.settings,
            settings_path=self.settings_path,
            user_dict_path=self.data_root / "medical_words.txt",
        )
        self._setup_tray()
        self._watcher = QFileSystemWatcher(self.app)
        if self.spool_dir.is_dir():
            self._watcher.addPath(str(self.spool_dir))
        self._watcher.directoryChanged.connect(self._scan_inbox)
        self._poll = QTimer(self.app)
        self._poll.setInterval(3000)
        self._poll.timeout.connect(self._scan_inbox)
        self._poll.start()
        self._update_thread: QThread | None = None
        with contextlib.suppress(ValueError):
            set_github_repo(self.settings.github_repo)

    def _setup_tray(self) -> None:
        self.tray = QSystemTrayIcon(QIcon.fromTheme("document-print"), self.app)
        self.tray.setToolTip(strings.TRAY_TIP)
        menu = QMenu()
        show = QAction(strings.TRAY_SHOW, self.app)
        show.triggered.connect(self.window.showNormal)
        update_act = QAction(strings.UPDATE, self.app)
        update_act.triggered.connect(self._open_update_dialog)
        quit_act = QAction(strings.TRAY_QUIT, self.app)
        quit_act.triggered.connect(self.app.quit)
        menu.addAction(show)
        menu.addAction(update_act)
        menu.addAction(quit_act)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _open_update_dialog(self) -> None:
        dialog = UpdateDialog(parent=self.window)
        dialog.start_check()
        dialog.exec()

    def _start_update_check(self) -> None:
        if not self.settings.check_updates_on_startup:
            return
        thread = QThread(self.app)
        worker = _StartupUpdateCheck()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        def on_finished(status: object) -> None:
            assert isinstance(status, dict)
            if status.get("available"):
                latest = status.get("latest_version") or "?"
                self.tray.showMessage(
                    strings.APP_NAME,
                    strings.UPDATE_AVAILABLE_TRAY.format(latest=latest),
                    QSystemTrayIcon.MessageIcon.Information,
                    8000,
                )
            thread.quit()

        worker.finished.connect(on_finished)
        self._update_thread = thread
        thread.start()


    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.window.showNormal()
            self.window.raise_()
            self.window.activateWindow()

    def _scan_inbox(self) -> None:
        for pdf in list_new_spool_pdfs(self.spool_dir, state_path=self.inbox_state):
            mark_processed(pdf, state_path=self.inbox_state)
            self.window.showNormal()
            self.window.raise_()
            self.window.handle_incoming_file(pdf)

    def run(self) -> int:
        self.window.show()
        self._scan_inbox()
        # Kurze Verzögerung, damit die UI zuerst erscheint.
        QTimer.singleShot(1500, self._start_update_check)
        return self.app.exec()


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName(strings.APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    server = _ensure_single_instance(app)
    if server is None:
        sys.exit(0)
    gw = GhostWriterApp(app)

    def on_new_connection() -> None:
        sock = server.nextPendingConnection()
        if sock:
            sock.readyRead.connect(lambda: gw.window.showNormal())

    server.newConnection.connect(on_new_connection)
    raise SystemExit(gw.run())


if __name__ == "__main__":
    main()
