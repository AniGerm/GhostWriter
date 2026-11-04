"""UI tests for print/cost dialog."""

from __future__ import annotations

import pytest
from ghostwriter.costs import CostSettings
from ghostwriter.ui.print_cost_dialog import PrintCostDialog, PrintItem

pytestmark = pytest.mark.qt


def test_auto_pages_and_total(qtbot) -> None:
    dialog = PrintCostDialog(
        letter_pages=2,
        befund=[
            PrintItem("1", "Befund A", 3, True),
            PrintItem("2", "Befund B", 1, True),
        ],
        cost_settings=CostSettings(),
    )
    qtbot.addWidget(dialog)
    assert dialog.page_count() == 6
    result = dialog.cost_result()
    # 6 * 0.50 + 25 = 28
    assert result.total == pytest.approx(28.0)
    # uncheck one
    dialog._checks[0][1].setChecked(False)
    dialog._pages.setValue(dialog._auto_pages())
    assert dialog.page_count() == 3
