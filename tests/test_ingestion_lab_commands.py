from gui.services.command_registry import global_command_registry
from gui.services.service_locator import services
import types


def setup_function(_fn):
    # Reset registry & services to avoid cross-test pollution
    global_command_registry.reset()
    services.clear()
    # Re-import module to auto-register commands
    import importlib
    mod = importlib.import_module("gui.services.ingestion_lab_commands")
    # Explicit registration to avoid relying on import side-effects in test isolation
    if hasattr(mod, "register_ingestion_lab_commands"):
        mod.register_ingestion_lab_commands()


def test_commands_registered():
    ids = {c.command_id for c in global_command_registry.list()}
    assert "ingestion_lab.open" in ids
    assert "ingestion_lab.apply_rules" in ids
    assert "ingestion_lab.rollback_previous_rule_version" in ids


def test_apply_rules_invokes_panel_method(monkeypatch):
    called = {}

    class Panel:
        def apply_current_rules(self):  # pragma: no cover - simple
            called["applied"] = True

    services.register("ingestion_lab_panel", Panel())
    # Ensure commands registered
    test_commands_registered()
    ok, err = global_command_registry.execute("ingestion_lab.apply_rules")
    assert ok and err is None
    assert called.get("applied") is True


def test_rollback_previous_loads_prev_version(monkeypatch):
    loaded = {}

    class Panel:
        def load_rules_text(self, text):  # pragma: no cover - simple
            loaded["text"] = text

    # Fake version entries
    prev_entry = types.SimpleNamespace(version_num=1, rules_json="{\"version\":1,\"a\":1}")
    latest_entry = types.SimpleNamespace(version_num=2, rules_json="{\"version\":1,\"a\":2}")

    class Store:
        def latest(self):  # pragma: no cover - simple
            return latest_entry

        def previous_version(self, v):  # pragma: no cover - simple
            return prev_entry if v == 2 else None

    services.register("ingestion_lab_panel", Panel(), allow_override=True)
    services.register("rule_version_store", Store(), allow_override=True)

    ok, err = global_command_registry.execute("ingestion_lab.rollback_previous_rule_version")
    assert ok and err is None, err
    assert loaded.get("text", "").startswith("{\"version\":1")