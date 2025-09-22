from gui.services.recent_teams import RecentTeamsTracker


def test_recent_tracker_add_and_order():
    r = RecentTeamsTracker(max_items=3)
    r.add("A")
    r.add("B")
    r.add("C")
    assert r.items() == ["C", "B", "A"]
    # Re-select B moves to front
    r.add("B")
    assert r.items() == ["B", "C", "A"]


def test_recent_tracker_trim_and_dedupe():
    r = RecentTeamsTracker(max_items=2)
    r.add("X")
    r.add("X")  # adjacent duplicate ignored
    assert r.items() == ["X"]
    r.add("Y")
    r.add("Z")  # triggers trim
    assert r.items() == ["Z", "Y"]
    r.add("Y")  # move existing to front
    assert r.items() == ["Y", "Z"]
