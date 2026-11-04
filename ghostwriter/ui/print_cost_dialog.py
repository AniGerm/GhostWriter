"""Druckdialog mit Seitenzahl und Kostenrechner."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ghostwriter.costs import CostBreakdown, CostSettings, calculate_costs
from ghostwriter.ui import strings


@dataclass(frozen=True, slots=True)
class PrintItem:
    document_id: str
    label: str
    page_count: int
    is_befund: bool


class PrintCostDialog(QDialog):
    def __init__(
        self,
        *,
        letter_pages: int,
        befund: list[PrintItem],
        cost_settings: CostSettings,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(strings.PRINT_AND_COST)
        self._cost_settings = cost_settings
        self._letter_pages = max(1, letter_pages)
        self._checks: list[tuple[PrintItem, QCheckBox]] = []

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(strings.EXCLUDE_ANFRAGE_HINT))
        layout.addWidget(QLabel(f"Schreiben: {self._letter_pages} Seite(n)"))

        for item in befund:
            cb = QCheckBox(f"{item.label} ({item.page_count} S.)")
            cb.setChecked(True)
            cb.toggled.connect(self._recalc)
            self._checks.append((item, cb))
            layout.addWidget(cb)

        form = QFormLayout()
        self._pages = QSpinBox()
        self._pages.setRange(0, 100000)
        self._pages.valueChanged.connect(self._recalc)
        form.addRow(strings.PAGES_MANUAL, self._pages)

        self._postage = QComboBox()
        self._postage.addItem("Kein Versand", None)
        for opt in cost_settings.postage_options:
            self._postage.addItem(f"{opt.label} ({opt.price:.2f} €)", opt.key)
        self._postage.currentIndexChanged.connect(self._recalc)
        form.addRow(strings.POSTAGE, self._postage)

        self._custom_postage = QDoubleSpinBox()
        self._custom_postage.setRange(-0.01, 100)
        self._custom_postage.setSpecialValueText("—")
        self._custom_postage.setValue(-0.01)
        self._custom_postage.setDecimals(2)
        self._custom_postage.valueChanged.connect(self._recalc)
        form.addRow("Versand manuell (€)", self._custom_postage)

        self._flat = QLabel()
        self._copy = QLabel()
        self._post = QLabel()
        self._total = QLabel()
        form.addRow(strings.FLAT_FEE, self._flat)
        form.addRow(strings.COPY_COST, self._copy)
        form.addRow("Versand (€)", self._post)
        form.addRow(strings.TOTAL, self._total)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(strings.PRINT)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._pages.setValue(self._auto_pages())
        self._recalc()

    def _auto_pages(self) -> int:
        total = self._letter_pages
        for item, cb in self._checks:
            if cb.isChecked():
                total += item.page_count
        return total

    def _recalc(self) -> None:
        # Checkbox-Änderungen aktualisieren die vorgeschlagene Seitenzahl.
        sender = self.sender()
        if sender is not None and any(sender is cb for _, cb in self._checks):
            self._pages.blockSignals(True)
            self._pages.setValue(self._auto_pages())
            self._pages.blockSignals(False)
        custom = self._custom_postage.value()
        custom_val = None if custom < 0 else custom
        result = calculate_costs(
            page_count=self._pages.value(),
            settings=self._cost_settings,
            postage_key=self._postage.currentData(),
            custom_postage=custom_val,
        )
        self._flat.setText(f"{result.flat_fee:.2f}")
        self._copy.setText(f"{result.copy_cost:.2f}")
        self._post.setText(f"{result.postage:.2f}")
        self._total.setText(f"{result.total:.2f}")
        self._last = result

    def selected_befund_ids(self) -> list[str]:
        return [item.document_id for item, cb in self._checks if cb.isChecked()]

    def cost_result(self) -> CostBreakdown:
        return self._last

    def page_count(self) -> int:
        return self._pages.value()
