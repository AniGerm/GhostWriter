"""Popup: eingehendes/importiertes Dokument einem Projekt zuordnen."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ghostwriter.store import DocumentRole, Project
from ghostwriter.ui import strings


class ImportDialog(QDialog):
    """Fragt Rolle und Zielprojekt ab."""

    def __init__(
        self,
        *,
        source_path: Path,
        projects: list[Project],
        suggested_role: DocumentRole = DocumentRole.BEFUND,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(strings.IMPORT_TITLE)
        self._source_path = source_path
        self._role = suggested_role

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(source_path.name))

        self._role_anfrage = QRadioButton(strings.ROLE_ANFRAGE)
        self._role_befund = QRadioButton(strings.ROLE_BEFUND)
        self._role_group = QButtonGroup(self)
        self._role_group.addButton(self._role_anfrage)
        self._role_group.addButton(self._role_befund)
        if suggested_role is DocumentRole.ANFRAGE:
            self._role_anfrage.setChecked(True)
        else:
            self._role_befund.setChecked(True)
        layout.addWidget(QLabel(strings.CHOOSE_ROLE))
        layout.addWidget(self._role_anfrage)
        layout.addWidget(self._role_befund)

        self._new_project = QRadioButton(strings.IMPORT_NEW_PROJECT)
        self._existing = QRadioButton(strings.IMPORT_EXISTING)
        self._target_group = QButtonGroup(self)
        self._target_group.addButton(self._new_project)
        self._target_group.addButton(self._existing)
        self._new_project.setChecked(True)
        layout.addWidget(self._new_project)
        layout.addWidget(self._existing)

        form = QFormLayout()
        self._patient = QLineEdit()
        self._reference = QLineEdit()
        form.addRow(strings.PATIENT_LABEL, self._patient)
        form.addRow(strings.REFERENCE, self._reference)
        layout.addLayout(form)

        self._project_combo = QComboBox()
        for project in projects:
            label = f"{project.patient_label} ({project.reference})".strip()
            self._project_combo.addItem(label, project.id)
        self._project_combo.setEnabled(bool(projects))
        if not projects:
            self._existing.setEnabled(False)
        layout.addWidget(self._project_combo)

        self._new_project.toggled.connect(self._toggle_mode)
        self._toggle_mode(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _toggle_mode(self, new_mode: bool) -> None:
        self._patient.setEnabled(new_mode)
        self._reference.setEnabled(new_mode)
        self._project_combo.setEnabled(not new_mode and self._project_combo.count() > 0)

    @property
    def source_path(self) -> Path:
        return self._source_path

    def selected_role(self) -> DocumentRole:
        if self._role_anfrage.isChecked():
            return DocumentRole.ANFRAGE
        return DocumentRole.BEFUND

    def creates_new_project(self) -> bool:
        return self._new_project.isChecked()

    def patient_label(self) -> str:
        return self._patient.text().strip() or self._source_path.stem

    def reference(self) -> str:
        return self._reference.text().strip()

    def existing_project_id(self) -> str | None:
        if self.creates_new_project():
            return None
        data = self._project_combo.currentData()
        return str(data) if data else None
