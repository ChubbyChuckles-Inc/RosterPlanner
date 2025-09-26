import os, json, pytest
from PyQt6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("RP_TEST_MODE", "1")

app = QApplication.instance() or QApplication([])


def test_quality_gates_integration(tmp_path, qtbot):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "sample.html").write_text(
        """
        <html><body>
        <ul class='p'>
            <li><span class='n'>Alice</span><span class='rank'>1</span></li>
            <li><span class='n'>Bob</span></li>
        </ul>
        </body></html>
        """,
        encoding="utf-8",
    )
    from gui.views.ingestion_lab_panel import IngestionLabPanel

    panel = IngestionLabPanel(base_dir=str(data_dir))
    qtbot.addWidget(panel)
    panel.refresh_file_list()
    rules = {
        "version": 1,
        "resources": {
            "players": {
                "kind": "list",
                "selector": "ul.p",
                "item_selector": "li",
                "fields": {"name": {"selector": "span.n"}, "rank": {"selector": "span.rank"}},
            }
        },
        "quality_gates": {"players.name": 1.0, "players.rank": 0.75},
    }
    panel.rule_editor.setPlainText(json.dumps(rules))
    panel._on_quality_gates_clicked()
    log_text = panel.log_area.toPlainText()
    # Should report FAIL because rank coverage is 0.5 < 0.75 threshold
    assert "Quality Gates Result: FAIL" in log_text
    assert "players.rank" in log_text
    assert "players.name" in log_text
