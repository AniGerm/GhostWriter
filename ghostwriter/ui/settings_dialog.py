"""Einstellungsdialog."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ghostwriter.settings import AppSettings
from ghostwriter.ui import strings


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(strings.SETTINGS)
        self._settings = settings

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._model = QLineEdit(settings.ollama_model)
        self._ctx = QSpinBox()
        self._ctx.setRange(2048, 131072)
        self._ctx.setValue(settings.ollama_num_ctx)
        self._flat = QDoubleSpinBox()
        self._flat.setRange(0, 1000)
        self._flat.setDecimals(2)
        self._flat.setValue(settings.flat_fee)
        self._tier_pages = QSpinBox()
        self._tier_pages.setRange(1, 10000)
        self._tier_pages.setValue(settings.copy_tier_up_to)
        self._tier_price = QDoubleSpinBox()
        self._tier_price.setRange(0, 10)
        self._tier_price.setDecimals(2)
        self._tier_price.setValue(settings.copy_tier_price)
        self._after = QDoubleSpinBox()
        self._after.setRange(0, 10)
        self._after.setDecimals(2)
        self._after.setValue(settings.after_last_tier_price)
        self._place = QLineEdit(settings.document_place)
        self._letterhead = QTextEdit(settings.letterhead_html)
        self._signature = QTextEdit(settings.signature_html)
        self._github = QLineEdit(settings.github_repo)

        form.addRow(strings.OLLAMA_MODEL, self._model)
        form.addRow(strings.OLLAMA_CTX, self._ctx)
        form.addRow(strings.FLAT_FEE, self._flat)
        form.addRow("Kopien bis Seite", self._tier_pages)
        form.addRow("Preis/Seite (€)", self._tier_price)
        form.addRow("Danach €/Seite", self._after)
        form.addRow(strings.GITHUB_REPO, self._github)
        form.addRow(strings.DOCUMENT_PLACE, self._place)
        form.addRow(strings.LETTERHEAD, self._letterhead)
        form.addRow(strings.SIGNATURE, self._signature)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def result_settings(self) -> AppSettings:
        s = self._settings
        s.ollama_model = self._model.text().strip() or s.ollama_model
        s.ollama_num_ctx = self._ctx.value()
        s.flat_fee = self._flat.value()
        s.copy_tier_up_to = self._tier_pages.value()
        s.copy_tier_price = self._tier_price.value()
        s.after_last_tier_price = self._after.value()
        s.document_place = self._place.text().strip()
        s.letterhead_html = self._letterhead.toPlainText()
        s.signature_html = self._signature.toPlainText()
        repo = self._github.text().strip()
        if repo:
            s.github_repo = repo
        return s
