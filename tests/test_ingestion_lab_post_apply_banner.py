import os
import sqlite3
from PyQt6.QtWidgets import QApplication
import pytest

from gui.views.ingestion_lab_panel import IngestionLabPanel
from gui.ingestion.rule_schema import RuleSet

# Minimal QApplication singleton for tests
app = QApplication.instance() or QApplication([])

RULES = {
    "version": 1,
    "resources": {
        "players": {
            "kind": "list",
            "selector": "ul.p",
            "item_selector": "li",
            "fields": {"name": {"selector": "span.n"}},
        }
    },
}

HTML_DOC = """
<html><body>
<ul class='p'>
  <li><span class='n'>Alice</span></li>
  <li><span class='n'>Bob</span></li>
</ul>
</body></html>
"""


def _write_tmp_html(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    f = d / "team_roster_sample.html"
    f.write_text(HTML_DOC, encoding="utf-8")
    return str(d), str(f)


def test_post_apply_banner_snapshot(tmp_path, monkeypatch):
    base_dir, fpath = _write_tmp_html(tmp_path)
    panel = IngestionLabPanel(base_dir=base_dir)
    panel.show()  # ensure widget hierarchy considered visible
    app.processEvents()
    # Insert rules
    import json

    panel.rule_editor.setPlainText(json.dumps(RULES))
    # Ensure file list includes our file
    assert any("team_roster_sample" in x for x in panel.listed_files())
    # Run simulate
    panel._on_simulate_clicked()
    assert panel._last_simulation_id is not None
    # Provide an sqlite connection in services fallback (monkeypatch service locator return None -> handled)
    panel._on_apply_clicked()
    snap = panel.apply_summary_snapshot()
    assert snap.get("inserted_total") == 2
    assert snap.get("sim_id") is not None
    # Banner should be visible with summary text
    # Parent panel may not be shown in headless CI; assert on text content instead
    assert "inserted_rows=2" in panel._banner.text()
