import os, json
from PyQt6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("RP_TEST_MODE", "1")

app = QApplication.instance() or QApplication([])


def test_orphan_fields_button(tmp_path, qtbot):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "sample.html").write_text(
        "<html><body><ul class='p'><li><span class='n'>A</span><span class='r'>1</span></li></ul></body></html>",
        encoding="utf-8",
    )
    from gui.views.ingestion_lab_panel import IngestionLabPanel

    panel = IngestionLabPanel(base_dir=str(data_dir))
    qtbot.addWidget(panel)
    # Provide rules with unmapped field 'rank'
    rules = {
        "version": 1,
        "resources": {
            "players": {
                "kind": "list",
                "selector": "ul.p",
                "item_selector": "li",
                "fields": {"name": {"selector": "span.n"}, "rank": {"selector": "span.r"}},
            }
        },
        # mapping only maps name
        "mapping": {"players": {"name": "player_name"}},
    }
    panel.rule_editor.setPlainText(json.dumps(rules))
    panel._on_orphan_fields_clicked()
    log_text = panel.log_area.toPlainText()
    assert "Orphans" in log_text
    assert "players.rank" in log_text
