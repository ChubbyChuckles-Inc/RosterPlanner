import pytest

from gui.services.shortcut_registry import ShortcutRegistry


def test_register_and_list_shortcuts():
    reg = ShortcutRegistry()
    assert reg.register("test.open", "Ctrl+O", "Open something", category="General")
    assert not reg.register("test.open", "Ctrl+Shift+O", "Duplicate id")
    entries = reg.list()
    assert len(entries) == 1 and entries[0].sequence == "Ctrl+O"
    cats = reg.by_category()
    assert "General" in cats and len(cats["General"]) == 1


def test_conflict_detection():
    reg = ShortcutRegistry()
    reg.register("a.one", "Ctrl+X", "One")
    reg.register("a.two", "Ctrl+X", "Two")  # same sequence
    reg.register("a.three", "Ctrl+Y", "Three")
    conflicts = reg.find_conflicts()
    assert "CTRL+X" in conflicts and len(conflicts["CTRL+X"]) == 2


def test_register_or_replace_and_unregister():
    reg = ShortcutRegistry()
    reg.register("macro.clean", "Ctrl+1", "Initial")
    reg.register_or_replace("macro.clean", "Ctrl+2", "Updated", category="Custom")
    entry = reg.get("macro.clean")
    assert entry is not None
    assert entry.sequence == "Ctrl+2"
    assert entry.description == "Updated"
    assert entry.category == "Custom"
    removed = reg.unregister("macro.clean")
    assert removed is True
    assert reg.get("macro.clean") is None
