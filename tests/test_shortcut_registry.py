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
