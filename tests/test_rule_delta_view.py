from gui.ingestion.rule_delta_view import (
    generate_delta_view,
    diff_resource,
)


def test_diff_resource_added_removed_changed():
    existing = [
        {"id": 1, "name": "Alice", "points": 10},
        {"id": 2, "name": "Bob", "points": 9},
    ]
    new = [
        {"id": 1, "name": "Alice", "points": 11},  # changed points
        {"id": 3, "name": "Carol", "points": 7},  # added
    ]
    res = diff_resource("team_roster", existing, new, key_fields=["id"])
    statuses = {d.status for d in res.deltas}
    assert statuses == {"changed", "removed", "added"}
    changed = next(d for d in res.deltas if d.status == "changed")
    assert changed.changed_fields == {"points": (10, 11)}
    removed = next(d for d in res.deltas if d.status == "removed")
    assert removed.old["id"] == 2
    added = next(d for d in res.deltas if d.status == "added")
    assert added.new["id"] == 3


def test_diff_resource_infer_key():
    # No explicit id, should infer unique field or combination
    existing = [
        {"team": "A", "points": 10},
        {"team": "B", "points": 12},
    ]
    new = [
        {"team": "A", "points": 10},
        {"team": "B", "points": 13},
        {"team": "C", "points": 8},
    ]
    res = diff_resource("ranking_table", existing, new)  # infer key -> ['points'] doesn't work (not unique); should pick ['points','team'] or ['team'] if team unique
    # Expect key_fields contains 'team'
    assert "team" in res.key_fields
    # There should be 3 keys total after union; one changed (team B)
    changed_rows = [d for d in res.deltas if d.status == "changed"]
    assert len(changed_rows) == 1
    assert changed_rows[0].changed_fields == {"points": (12, 13)}


def test_generate_delta_view_multi_resource():
    existing = {
        "ranking_table": [{"team": "A", "points": 10}],
        "team_roster": [{"id": 1, "name": "Alice"}],
    }
    new = {
        "ranking_table": [{"team": "A", "points": 11}],  # changed
        "team_roster": [{"id": 1, "name": "Alice"}],  # unchanged
        "new_resource": [{"id": 99}],  # added resource
    }
    view = generate_delta_view(existing, new)
    # resources sorted alpha
    resource_names = [r.resource for r in view.resources]
    assert resource_names == ["new_resource", "ranking_table", "team_roster"]
    rt = next(r for r in view.resources if r.resource == "ranking_table")
    assert any(d.status == "changed" for d in rt.deltas)
    tr = next(r for r in view.resources if r.resource == "team_roster")
    assert any(d.status == "unchanged" for d in tr.deltas)
    nr = next(r for r in view.resources if r.resource == "new_resource")
    assert any(d.status == "added" for d in nr.deltas)
