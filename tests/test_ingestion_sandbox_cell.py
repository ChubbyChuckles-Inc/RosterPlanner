import os
import pytest
from PyQt6.QtWidgets import QApplication

from gui.views.ingestion_lab_panel import IngestionLabPanel


@pytest.mark.gui
def test_sandbox_cell_basic(tmp_path):
    # Ensure Qt app exists
    if QApplication.instance() is None:  # pragma: no cover - test harness creation
        _ = QApplication([])
    panel = IngestionLabPanel(base_dir=str(tmp_path))
    # Minimal ruleset with list resource
    panel.rule_editor.setPlainText(
        '{"resources": {"players": {"kind": "list", "selector": "div.roster", "item_selector": "div.player", "fields": {"name": ".name"}}}}'
    )
    # Open sandbox
    panel.btn_sandbox.click()
    assert panel._sandbox_widget.isVisible()
    # Provide fragment
    fragment = "<div class='roster'><div class='player'><span class='name'>Alice</span></div><div class='player'><span class='name'>Bob</span></div></div>"
    panel.sandbox_html.setPlainText(fragment)
    panel.sandbox_resource.setText("players")
    panel.btn_sandbox_run.click()
    log = panel.log_area.toPlainText()
    assert "Sandbox Result" in log
    assert "rows=2" in log
