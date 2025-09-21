from __future__ import annotations

import pytest

from gui.testing import (
    compute_logical_focus_order,
    focus_order_names,
    tab_traversal_names,
)

try:
    from PyQt6.QtWidgets import (
        QWidget,
        QVBoxLayout,
        QLineEdit,
        QPushButton,
        QCheckBox,
        QLabel,
        QApplication,
    )
    from PyQt6.QtCore import Qt

    PYQT_AVAILABLE = True
except Exception:  # pragma: no cover - environment without PyQt
    PYQT_AVAILABLE = False


pytestmark = pytest.mark.skipif(
    not PYQT_AVAILABLE, reason="PyQt6 not available for real focus traversal test"
)


def _composite_widget_factory():  # Factory returning a QWidget
    root = QWidget()
    layout = QVBoxLayout(root)
    # Non-focusable label first (should be skipped)
    title = QLabel("Title")
    title.setObjectName("lbl_title")
    layout.addWidget(title)

    le1 = QLineEdit()
    le1.setObjectName("input_first")
    layout.addWidget(le1)

    btn = QPushButton("Submit")
    btn.setObjectName("btn_submit")
    layout.addWidget(btn)

    chk = QCheckBox("Remember")
    chk.setObjectName("chk_remember")
    layout.addWidget(chk)

    le2 = QLineEdit()
    le2.setObjectName("input_second")
    layout.addWidget(le2)

    # Disabled field (should not appear in order)
    disabled = QLineEdit()
    disabled.setObjectName("input_disabled")
    disabled.setEnabled(False)
    layout.addWidget(disabled)

    return root


def test_logical_and_real_tab_order_align():
    logical_entries = compute_logical_focus_order(_composite_widget_factory)
    logical_names = focus_order_names(logical_entries)
    real_names = tab_traversal_names(_composite_widget_factory)

    # Expectations: label skipped, disabled input skipped
    # Typical Qt tab order = creation order of focusable widgets
    expected_subset = [
        "input_first",
        "btn_submit",
        "chk_remember",
        "input_second",
    ]
    # Logical list contains exactly these
    assert logical_names == expected_subset
    # Real traversal should contain at least these in the same order (cycle may repeat start)
    assert real_names[: len(expected_subset)] == expected_subset
