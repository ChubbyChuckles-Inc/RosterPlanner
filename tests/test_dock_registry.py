import pytest

from gui.views import dock_registry


def test_duplicate_registration_raises():
    # Local sandbox: register a temp id then attempt duplicate
    dock_id = "_dup_test"

    def factory():
        return object()

    if not dock_registry.is_registered(dock_id):
        dock_registry.register_dock(dock_id, "Dup", factory)  # type: ignore[attr-defined]
    with pytest.raises(ValueError):
        dock_registry.register_dock(dock_id, "Dup2", factory)  # type: ignore[attr-defined]


def test_iter_definitions_contains_core_after_ensure(monkeypatch):
    collected = {}

    def fake_factory():
        return object()

    factories = {
        cid: fake_factory
        for cid in ["navigation", "availability", "detail", "stats", "planner", "logs"]
    }
    dock_registry.ensure_core_docks_registered(factories)
    ids = {d.dock_id for d in dock_registry.iter_definitions()}
    for cid in factories:
        assert cid in ids


def test_plugin_hook_extension(monkeypatch):
    # Define plugin hook that registers a new dock id
    new_id = "plugin_extra"

    def plugin_hook():
        if not dock_registry.is_registered(new_id):

            def f():
                return object()

            dock_registry.register_dock(new_id, "Plugin Extra", f)  # type: ignore[attr-defined]

    dock_registry.PLUGIN_HOOKS.append(plugin_hook)
    dock_registry.run_plugin_hooks()
    assert dock_registry.is_registered(new_id)
