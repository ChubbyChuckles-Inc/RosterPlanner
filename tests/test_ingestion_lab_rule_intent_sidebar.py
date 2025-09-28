import json

from PyQt6.QtWidgets import QApplication

from gui.views.ingestion_lab.panel import IngestionLabPanel


def _combo_items(widget):
    return [widget.itemText(i) for i in range(widget.count())]


def test_intent_sidebar_populates_and_saves(tmp_path, qtbot):
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    panel = IngestionLabPanel(base_dir=str(tmp_path))
    qtbot.addWidget(panel)

    rules = {
        "version": 1,
        "resources": {
            "players": {
                "kind": "list",
                "selector": "div.player",
                "item_selector": "div.row",
                "fields": {"name": {"selector": "span.name"}},
            },
            "teams": {
                "kind": "table",
                "selector": "table.teams",
                "columns": ["Name", "Points"],
            },
        },
    }

    panel.rule_editor.setPlainText(json.dumps(rules))
    panel._refresh_intent_resources()

    combo = panel._intent_sidebar.resource_combo
    assert _combo_items(combo) == ["players", "teams"]
    assert panel._intent_sidebar.current_resource() == "players"

    panel._intent_sidebar.purpose_edit.setText("  Document roster workflow  ")
    panel._intent_sidebar.assumptions_edit.setPlainText("requires stable layout")
    panel._intent_sidebar.todo_edit.setPlainText("  add win streak column  ")
    payload = panel._intent_sidebar.current_payload()
    panel._on_intent_save("players", payload)

    stored = panel._intent_store.get("players")
    assert stored.purpose == "Document roster workflow"
    assert stored.assumptions == "requires stable layout"
    assert stored.todo == "add win streak column"

    assert panel._intent_sidebar.purpose_edit.text() == "Document roster workflow"
    assert panel._intent_sidebar.assumptions_edit.toPlainText() == "requires stable layout"
    assert panel._intent_sidebar.todo_edit.toPlainText() == "add win streak column"

    payload_disk = json.loads(
        (tmp_path / ".ingestion_rule_intents.json").read_text(encoding="utf-8")
    )
    assert payload_disk["resources"]["players"]["purpose"] == "Document roster workflow"

    # Clearing fields should remove persisted entry and leave UI blank
    panel._intent_sidebar.purpose_edit.setText("")
    panel._intent_sidebar.assumptions_edit.setPlainText(" ")
    panel._intent_sidebar.todo_edit.setPlainText("")
    panel._on_intent_save("players", panel._intent_sidebar.current_payload())

    assert panel._intent_store.resources() == {}
    assert panel._intent_sidebar.purpose_edit.text() == ""
    assert panel._intent_sidebar.todo_edit.toPlainText() == ""

    # Update rule set to remove players resource and ensure sidebar updates
    new_rules = {
        "version": 1,
        "resources": {
            "teams": {
                "kind": "table",
                "selector": "table.teams",
                "columns": ["Name", "Points"],
            }
        },
    }
    panel.rule_editor.setPlainText(json.dumps(new_rules))
    panel._refresh_intent_resources()

    assert _combo_items(combo) == ["teams"]
    assert panel._intent_sidebar.current_resource() == "teams"
    assert panel._intent_current_resource == "teams"

    panel.close()
