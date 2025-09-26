from __future__ import annotations

from gui.services.accessibility_audit import audit_widget_tree
from gui.views.ingestion_lab_panel import IngestionLabPanel
from gui.ingestion.selector_picker import SelectorPickerDialog
import os
import pytest


@pytest.mark.skipif("PyQt6" not in globals(), reason="PyQt6 not available")
def test_ingestion_lab_accessibility_basic(qtbot):  # type: ignore
    panel = IngestionLabPanel(base_dir="data")
    qtbot.addWidget(panel)  # type: ignore
    rep = panel.run_accessibility_audit()
    # Expect no missing focus policies for named buttons and no unnamed interactive widgets
    assert rep is not None
    assert "ingLabBtnRefresh" not in rep.missing_focus
    # At least one interactive widget present
    assert rep.meta["interactive"] > 0


@pytest.mark.skipif("PyQt6" not in globals(), reason="PyQt6 not available")
def test_selector_picker_accessibility(qtbot):  # type: ignore
    html = '<html><body><div id="root" class="c1"><span class="c2">X</span></div></body></html>'
    dlg = SelectorPickerDialog(html)
    qtbot.addWidget(dlg)  # type: ignore
    rep = audit_widget_tree(dlg)
    # The tree and buttons should have object names after modifications
    assert "selectorPickerTree" not in rep.unnamed_interactive
    assert rep.meta["interactive"] > 0
