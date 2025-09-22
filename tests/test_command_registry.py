import pytest

from gui.services.command_registry import CommandRegistry


def test_register_and_list():
    reg = CommandRegistry()
    called = []
    assert reg.register("app.refresh", "Refresh", lambda: called.append(1))
    assert not reg.register("app.refresh", "Refresh Again", lambda: None)  # duplicate
    entries = reg.list()
    assert len(entries) == 1
    assert entries[0].command_id == "app.refresh"
    assert reg.is_registered("app.refresh")


def test_search_basic():
    reg = CommandRegistry()
    reg.register("app.open", "Open Something", lambda: None)
    reg.register("player.search", "Search Players", lambda: None)
    reg.register("team.open", "Open Team", lambda: None)
    results = reg.search("open")
    ids = [e.command_id for e in results]
    assert "app.open" in ids and "team.open" in ids
    # Fuzzy subsequence: 'ps' should match 'player.search'
    fuzzy = reg.search("ps")
    fuzzy_ids = [e.command_id for e in fuzzy]
    assert "player.search" in fuzzy_ids
    # Non-match returns empty
    assert reg.search("zzz") == []
    # Query empty returns all limited
    all_results = reg.search("")
    assert len(all_results) == 3


def test_execute_success():
    reg = CommandRegistry()
    flag = {"x": False}

    def cb():
        flag["x"] = True

    reg.register("toggle.flag", "Toggle Flag", cb)
    ok, err = reg.execute("toggle.flag")
    assert ok and err is None and flag["x"] is True


def test_execute_missing():
    reg = CommandRegistry()
    ok, err = reg.execute("nope")
    assert not ok and "not found" in err.lower()
