import json

from PyQt6.QtWidgets import QApplication

from gui.views.ingestion_lab.panel import IngestionLabPanel


HTML_FULL = """
<html><body>
  <div class='players'>
    <div class='row'><span class='name'>Alice</span></div>
    <div class='row'><span class='name'>Bob</span></div>
  </div>
</body></html>
"""

HTML_EMPTY = """
<html><body>
  <div class='players'></div>
</body></html>
"""


def test_watchlist_integration_runs_and_alerts(tmp_path, qtbot):
    data_file = tmp_path / "team.html"
    data_file.write_text(HTML_FULL, encoding="utf-8")

    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    panel = IngestionLabPanel(base_dir=str(tmp_path))
    qtbot.addWidget(panel)

    rules = {
        "version": 1,
        "resources": {
            "team": {
                "kind": "list",
                "selector": "div.players",
                "item_selector": "div.row",
                "fields": {"name": {"selector": ".name"}},
            }
        },
    }
    panel.rule_editor.setPlainText(json.dumps(rules))
    panel._refresh_intent_resources()

    panel._on_watchlist_add_requested("team", "field", "name", 50)
    panel._run_watchlist_check()

    snapshot = panel.watchlist_snapshot()
    assert snapshot["entries"][0]["baseline"] == 2
    assert not snapshot["results"][0]["alert"]

    data_file.write_text(HTML_EMPTY, encoding="utf-8")
    panel._run_watchlist_check()

    snapshot = panel.watchlist_snapshot()
    assert snapshot["results"][0]["alert"]
    assert snapshot["results"][0]["current"] == 0

    panel.close()
