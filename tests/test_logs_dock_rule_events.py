from gui.services.event_bus import EventBus, GUIEvent
from gui.services.service_locator import services


class FakeLogArea:
    def __init__(self):
        self.lines: list[str] = []

    def appendPlainText(self, text: str):  # pragma: no cover - trivial
        self.lines.append(text)


def test_rule_validation_failed_event_emitted(monkeypatch):
    """_append_log should emit RULE_VALIDATION_FAILED when containing phrase."""
    # Prepare service locator with event bus
    bus = EventBus()
    services.register("event_bus", bus, allow_override=True)
    captured: list[str] = []

    def handler(evt):  # pragma: no cover - simple
        captured.append(evt.payload.get("error"))  # type: ignore

    bus.subscribe(GUIEvent.RULE_VALIDATION_FAILED, handler)

    # Build minimal ingestion lab substitute with only log_area and _append_log bound method.
    from gui.views.ingestion_lab_panel import IngestionLabPanel
    import types

    dummy = types.SimpleNamespace()
    dummy.log_area = FakeLogArea()
    # Borrow the real method (unbound), then bind to dummy
    real_method = IngestionLabPanel._append_log
    bound = types.MethodType(real_method, dummy)
    bound("Rule validation failed: Missing field 'players'")

    assert captured and "Missing field" in captured[0]


def test_logs_dock_filters(monkeypatch):
    """Simulate events and ensure only selected ones would be appended (model logic)."""
    bus = EventBus()
    services.register("event_bus", bus, allow_override=True)
    appended: list[str] = []

    # Simulate filtering logic extracted from MainWindow implementation
    def on_event(evt):  # pragma: no cover - simple
        if evt.name == GUIEvent.INGEST_RULES_APPLIED.value:
            appended.append("applied")
        elif evt.name == GUIEvent.RULE_VALIDATION_FAILED.value:
            appended.append("failed")

    bus.subscribe(GUIEvent.INGEST_RULES_APPLIED, on_event)
    bus.subscribe(GUIEvent.RULE_VALIDATION_FAILED, on_event)

    bus.publish(GUIEvent.INGEST_RULES_APPLIED, {"rule_version": 3, "parsed": 5, "skipped": 0})
    bus.publish(GUIEvent.RULE_VALIDATION_FAILED, {"error": "Rule validation failed: X"})

    assert appended == ["applied", "failed"]