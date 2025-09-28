import json

from PyQt6.QtWidgets import QApplication

from gui.views.ingestion_lab_panel import IngestionLabPanel


def test_example_rows_preview_output(tmp_path, qtbot):
    _app = QApplication.instance()
    if _app is None:
        _app = QApplication([])

    panel = IngestionLabPanel(base_dir=str(tmp_path))
    qtbot.addWidget(panel)

    rules = {
        "version": 1,
        "resources": {
            "players": {
                "kind": "list",
                "selector": "div.player",
                "item_selector": "div.row",
                "fields": {
                    "name": {"selector": "span.name", "transforms": [{"kind": "trim"}]},
                    "rating": {
                        "selector": "span.rating",
                        "transforms": [{"kind": "trim"}, {"kind": "to_number"}],
                    },
                },
            }
        },
    }
    panel.rule_editor.setPlainText(json.dumps(rules))

    panel._on_example_rows_clicked()
    preview = panel.preview_area.toPlainText()

    assert "Example Data Rows" in preview
    assert "Resource: players" in preview
    assert "rating" in preview

    panel.close()
