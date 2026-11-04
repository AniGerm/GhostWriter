"""Hauptfenster: Projektliste und Projektansicht."""

from __future__ import annotations

import contextlib
from pathlib import Path

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QAction, QPageSize
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ghostwriter.extract import ExtractionResult
from ghostwriter.settings import AppSettings, save_settings
from ghostwriter.store import DocumentRole, ProjectStore, Question
from ghostwriter.ui import strings
from ghostwriter.ui.editor import ReportEditor
from ghostwriter.ui.import_dialog import ImportDialog
from ghostwriter.ui.print_cost_dialog import PrintCostDialog, PrintItem
from ghostwriter.ui.settings_dialog import SettingsDialog
from ghostwriter.ui.update_dialog import UpdateDialog
from ghostwriter.ui.workers import ExtractWorker, GenerateWorker
from ghostwriter.updates import set_github_repo


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        store: ProjectStore,
        settings: AppSettings,
        settings_path: Path,
        user_dict_path: Path,
    ) -> None:
        super().__init__()
        self.setWindowTitle(strings.APP_NAME)
        self.resize(1200, 800)
        self._store = store
        self._settings = settings
        self._settings_path = settings_path
        self._user_dict_path = user_dict_path
        self._current_id: str | None = None
        self._threads: list[QThread] = []

        self._project_list = QListWidget()
        self._project_list.currentItemChanged.connect(self._on_project_selected)

        self._docs = QListWidget()
        self._notes = QTextEdit()
        self._notes.setPlaceholderText(strings.NOTES)
        self._questions = QListWidget()
        self._editor = ReportEditor(user_dict_path=user_dict_path)

        right = QWidget()
        rlayout = QVBoxLayout(right)
        rlayout.addWidget(QLabel(strings.NOTES))
        rlayout.addWidget(self._notes, 1)
        rlayout.addWidget(QLabel("Dokumente"))
        rlayout.addWidget(self._docs, 1)
        qrow = QHBoxLayout()
        qrow.addWidget(QLabel(strings.QUESTIONS))
        add_q = QPushButton(strings.ADD_QUESTION)
        add_q.clicked.connect(self._add_question)
        qrow.addWidget(add_q)
        rlayout.addLayout(qrow)
        rlayout.addWidget(self._questions, 1)
        rlayout.addWidget(QLabel(strings.DRAFT))
        rlayout.addWidget(self._editor, 3)

        splitter = QSplitter()
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.addWidget(QLabel(strings.PROJECTS))
        ll.addWidget(self._project_list)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 3)
        self.setCentralWidget(splitter)

        with contextlib.suppress(ValueError):
            set_github_repo(settings.github_repo)
        self._build_toolbar()
        self.refresh_projects()

    def _build_toolbar(self) -> None:
        bar = QToolBar()
        self.addToolBar(bar)
        actions = [
            (strings.NEW_PROJECT, self._new_project),
            (strings.IMPORT_FILE, self._import_file),
            (strings.GENERATE, self._generate),
            (strings.PRINT_AND_COST, self._print_and_cost),
            (strings.UPDATE, self._open_updates),
            (strings.SETTINGS, self._open_settings),
            (strings.SAVE, self._save_current),
        ]
        for label, slot in actions:
            act = QAction(label, self)
            act.triggered.connect(slot)
            bar.addAction(act)

    def refresh_projects(self) -> None:
        self._project_list.clear()
        for project in self._store.list_projects():
            item = QListWidgetItem(f"{project.patient_label} — {project.reference}")
            item.setData(Qt.ItemDataRole.UserRole, project.id)
            self._project_list.addItem(item)

    def _on_project_selected(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is None:
            self._current_id = None
            return
        self._save_current()
        self._current_id = str(current.data(Qt.ItemDataRole.UserRole))
        self._load_project(self._current_id)

    def _load_project(self, project_id: str) -> None:
        project = self._store.get_project(project_id)
        if project is None:
            return
        self._notes.setPlainText(project.notes)
        self._editor.set_html(project.draft_html)
        self._docs.clear()
        for doc in self._store.list_documents(project_id):
            self._docs.addItem(f"[{doc.role.value}] {doc.display_name}")
        self._questions.clear()
        for q in self._store.get_questions(project_id):
            self._questions.addItem(f"{q.number}. [{q.keyword}] {q.text}")

    def _save_current(self) -> None:
        if not self._current_id:
            return
        self._store.set_notes(self._current_id, self._notes.toPlainText())
        self._store.set_draft_html(self._current_id, self._editor.to_html())
        questions = self._parse_questions_from_list()
        self._store.set_questions(self._current_id, questions)

    def _parse_questions_from_list(self) -> list[Question]:
        result: list[Question] = []
        for i in range(self._questions.count()):
            text = self._questions.item(i).text()
            # "1. [kw] body"
            try:
                num_part, rest = text.split(".", 1)
                number = int(num_part.strip())
                rest = rest.strip()
                keyword = ""
                if rest.startswith("[") and "]" in rest:
                    keyword, body = rest[1:].split("]", 1)
                    body = body.strip()
                else:
                    body = rest
                result.append(Question(number=number, text=body, keyword=keyword))
            except ValueError:
                result.append(Question(number=i + 1, text=text, keyword=""))
        return result

    def _new_project(self) -> None:
        label, ok = QInputDialog.getText(self, strings.NEW_PROJECT, strings.PATIENT_LABEL)
        if not ok or not label.strip():
            return
        ref, ok2 = QInputDialog.getText(self, strings.NEW_PROJECT, strings.REFERENCE)
        if not ok2:
            return
        project = self._store.create_project(patient_label=label.strip(), reference=ref.strip())
        self.refresh_projects()
        self._select_project(project.id)

    def _select_project(self, project_id: str) -> None:
        for i in range(self._project_list.count()):
            item = self._project_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == project_id:
                self._project_list.setCurrentItem(item)
                break

    def _import_file(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            strings.IMPORT_FILE,
            "",
            "PDF/Bilder (*.pdf *.png *.jpg *.jpeg *.tif *.tiff)",
        )
        if not path_str:
            return
        self.handle_incoming_file(Path(path_str))

    def handle_incoming_file(self, path: Path) -> None:
        projects = self._store.list_projects()
        suggested = DocumentRole.ANFRAGE
        lower = path.name.lower()
        if any(k in lower for k in ("befund", "arzt", "klinik")):
            suggested = DocumentRole.BEFUND
        elif any(k in lower for k in ("anfrage", "landrat", "sgb", "gdb")):
            suggested = DocumentRole.ANFRAGE
        else:
            suggested = DocumentRole.BEFUND
        dialog = ImportDialog(
            source_path=path,
            projects=projects,
            suggested_role=suggested,
            parent=self,
        )
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        if dialog.creates_new_project():
            project = self._store.create_project(
                patient_label=dialog.patient_label(),
                reference=dialog.reference(),
            )
            project_id = project.id
        else:
            existing_id = dialog.existing_project_id()
            if not existing_id:
                return
            project_id = existing_id
        try:
            doc = self._store.add_document(
                project_id,
                dialog.source_path,
                dialog.selected_role(),
                dialog.source_path.name,
            )
        except ValueError as exc:
            QMessageBox.warning(self, strings.APP_NAME, str(exc))
            return
        self.refresh_projects()
        self._select_project(project_id)
        self._start_extract(doc.id, Path(doc.stored_path), project_id)

    def _start_extract(self, document_id: str, path: Path, project_id: str) -> None:
        work = self._store.root / "projects" / project_id / "ocr" / document_id
        thread = QThread(self)
        worker = ExtractWorker(path, work)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        def on_finished(result: object) -> None:
            assert isinstance(result, ExtractionResult)
            self._store.update_document_text(document_id, result.text, result.page_count)
            self._load_project(project_id)
            thread.quit()

        def on_failed(name: str) -> None:
            QMessageBox.warning(self, strings.APP_NAME, f"Extraktion fehlgeschlagen ({name})")
            thread.quit()

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        thread.finished.connect(worker.deleteLater)
        self._threads.append(thread)
        thread.start()

    def _add_question(self) -> None:
        text, ok = QInputDialog.getText(self, strings.ADD_QUESTION, "Fragetext")
        if not ok or not text.strip():
            return
        n = self._questions.count() + 1
        self._questions.addItem(f"{n}. [] {text.strip()}")

    def _generate(self) -> None:
        if not self._current_id:
            return
        self._save_current()
        docs = self._store.list_documents(self._current_id)
        anfrage = next((d for d in docs if d.role is DocumentRole.ANFRAGE), None)
        if anfrage is None or not anfrage.extracted_text:
            QMessageBox.information(
                self,
                strings.APP_NAME,
                "Bitte zuerst eine Anfrage importieren und extrahieren.",
            )
            return
        findings = [
            (d.display_name, d.extracted_text)
            for d in docs
            if d.role is DocumentRole.BEFUND and d.extracted_text
        ]
        questions = self._store.get_questions(self._current_id) or None
        thread = QThread(self)
        worker = GenerateWorker(
            settings=self._settings,
            anfrage_text=anfrage.extracted_text,
            findings=findings,
            notes=self._notes.toPlainText(),
            questions=questions,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        def on_questions(qs: object) -> None:
            assert isinstance(qs, list)
            self._store.set_questions(self._current_id or "", qs)
            self._load_project(self._current_id or "")

        def on_finished(html: str) -> None:
            self._editor.set_html(html)
            self._save_current()
            thread.quit()

        def on_failed(name: str) -> None:
            QMessageBox.warning(self, strings.APP_NAME, f"KI-Erzeugung fehlgeschlagen ({name})")
            thread.quit()

        worker.questions_ready.connect(on_questions)
        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        self._threads.append(thread)
        thread.start()

    def _print_and_cost(self) -> None:
        if not self._current_id:
            return
        self._save_current()
        docs = self._store.list_documents(self._current_id)
        befund_items = [
            PrintItem(
                document_id=d.id,
                label=d.display_name,
                page_count=max(1, d.page_count),
                is_befund=True,
            )
            for d in docs
            if d.role is DocumentRole.BEFUND
        ]
        dialog = PrintCostDialog(
            letter_pages=self._editor.page_count_estimate(),
            befund=befund_items,
            cost_settings=self._settings.to_cost_settings(),
            parent=self,
        )
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        result = dialog.cost_result()
        self._store.save_cost_snapshot(
            self._current_id,
            page_count=result.page_count,
            flat_fee=result.flat_fee,
            copy_cost=result.copy_cost,
            postage=result.postage,
            total=result.total,
        )
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        print_dialog = QPrintDialog(printer, self)
        if print_dialog.exec() != print_dialog.DialogCode.Accepted:
            return
        self._editor._edit.document().print_(printer)

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self._settings, parent=self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        self._settings = dialog.result_settings()
        save_settings(self._settings_path, self._settings)
        with contextlib.suppress(ValueError):
            set_github_repo(self._settings.github_repo)

    def _open_updates(self) -> None:
        dialog = UpdateDialog(parent=self)
        dialog.start_check()
        dialog.exec()

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._save_current()
        super().closeEvent(event)
