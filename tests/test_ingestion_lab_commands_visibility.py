from gui.services.command_registry import global_command_registry
from gui.services.service_locator import services


def test_ingestion_lab_commands_visible_after_ingest_commands_import():
    # Reset for isolation
    global_command_registry.reset()
    services.clear()
    import importlib

    importlib.import_module("gui.services.ingest_commands")
    ids = {c.command_id for c in global_command_registry.list()}
    assert "ingestion_lab.open" in ids
    assert "ingestion_lab.apply_rules" in ids
    assert "ingestion_lab.rollback_previous_rule_version" in ids