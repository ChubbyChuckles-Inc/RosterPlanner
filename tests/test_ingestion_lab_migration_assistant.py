import dataclasses
import json
import os
import sqlite3
import sys

from PyQt6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("RP_TEST_MODE", "1")

if sys.version_info < (3, 10):
    _orig_dataclass = dataclasses.dataclass

    def _dataclass_py38(*args, **kwargs):
        kwargs.pop("slots", None)
        return _orig_dataclass(*args, **kwargs)

    dataclasses.dataclass = _dataclass_py38  # type: ignore[attr-defined]

app = QApplication.instance() or QApplication([])


def test_migration_assistant_suggests_mapping(tmp_path, qtbot):
    from gui.services.service_locator import services
    from gui.views.ingestion_lab.panel import IngestionLabPanel

    rules = {
        "version": 1,
        "resources": {
            "players": {
                "kind": "list",
                "selector": "ul.p",
                "item_selector": "li",
                "fields": {
                    "name": {"selector": "span.n"},
                    "rank": {"selector": "span.r"},
                },
            }
        },
        "mapping": {"players": {"name": "name"}},
    }

    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE players (name TEXT)")

    with services.override_context(sqlite_conn=conn):
        panel = IngestionLabPanel(base_dir=str(tmp_path))
        qtbot.addWidget(panel)
        panel.rule_editor.setPlainText(json.dumps(rules))
        panel._on_migration_assistant_clicked()

        log_text = panel.log_area.toPlainText()
        assert "Migration Assistant" in log_text
        assert "players.rank" in log_text

        preview_text = panel.preview_area.toPlainText()
        assert '"rank": "rank"' in preview_text

        snapshot = panel.migration_assistant_snapshot()
        assert snapshot["suggestions"]["players"]["rank"] == "rank"

    conn.close()
