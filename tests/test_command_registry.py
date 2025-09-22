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


def test_recency_and_frequency_weighting_affects_ordering():
    """Ensure that recently/frequently executed commands are boosted in search results.

    Strategy:
        - Register three commands with similar fuzzy match baseline for query 'open'.
        - Execute one command multiple times; execute another once very recently.
        - Search and assert boosted commands appear earlier than untouched.
    """
    reg = CommandRegistry()
    reg.register("alpha.open", "Open Alpha", lambda: None)
    reg.register("beta.open", "Open Beta", lambda: None)
    reg.register("gamma.open", "Open Gamma", lambda: None)
    # Initial ordering (baseline) - collect for sanity
    base_ids = [e.command_id for e in reg.search("open")]
    assert set(base_ids) == {"alpha.open", "beta.open", "gamma.open"}
    # Execute beta twice (frequency boost) and gamma once (recency boost most recent)
    reg.execute("beta.open")
    reg.execute("beta.open")
    reg.execute("gamma.open")  # most recent
    ordered_ids = [e.command_id for e in reg.search("open")]
    # gamma should appear before beta (most recent), beta before alpha due to frequency
    gamma_index = ordered_ids.index("gamma.open")
    beta_index = ordered_ids.index("beta.open")
    alpha_index = ordered_ids.index("alpha.open")
    assert gamma_index < beta_index < alpha_index
