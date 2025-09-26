from PyQt6.QtWidgets import QApplication
import json
from gui.views.ingestion_lab_panel import IngestionLabPanel
from gui.services.event_bus import GUIEvent, EventBus
from gui.services.service_locator import services

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

HTML = """
<html><body>
<ul class='p'>
  <li><span class='n'>A</span></li>
  <li><span class='n'>B</span></li>
</ul>
</body></html>
"""


def test_ingest_rules_applied_event(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    f = data_dir / "team_roster_x.html"
    f.write_text(HTML, encoding="utf-8")
    # Ensure EventBus present
    bus = services.try_get("event_bus")
    if bus is None:
        bus = EventBus()
        services.register("event_bus", bus)
    captured = {}

    def _handler(evt):
        if evt.name == GUIEvent.INGEST_RULES_APPLIED.value:
            captured.update(evt.payload or {})

    bus.subscribe(GUIEvent.INGEST_RULES_APPLIED, _handler)
    panel = IngestionLabPanel(base_dir=str(data_dir))
    panel.rule_editor.setPlainText(json.dumps(RULES))
    panel._on_simulate_clicked()
    panel._on_apply_clicked()
    assert captured.get("inserted_total") == 2
    assert captured.get("rows_by_resource", {}).get("players") == 2
