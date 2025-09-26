import sqlite3
import time

from gui.ingestion.rule_schema import RuleSet
from gui.ingestion.rule_apply_guard import SafeApplyGuard


HTML = """
<html><body>
<table class='r'><tr><th>Team</th><th>Pts</th></tr>
<tr><td>A</td><td>5</td></tr>
<tr><td>B</td><td>7</td></tr>
</table>
<ul class='players'>
  <li data-rank="1">Alice</li>
  <li data-rank="2">Bob</li>
</ul>
</body></html>
"""


def _multi_ruleset():
    return RuleSet.from_mapping(
        {
            "resources": {
                "ranking": {"kind": "table", "selector": "table.r", "columns": ["team", "pts"]},
                "players": {
                    "kind": "list",
                    "selector": "ul.players",
                    "item_selector": "li",
                    "fields": {
                        # Use tag name 'li' to capture the text of each list item
                        "name": {"selector": "li"},
                        "rank": {"selector": "@data-rank", "transforms": ["to_number"]},
                    },
                },
            }
        }
    )


def test_apply_integration_multi_resource_and_audit():
    """Simulate/apply multi-resource ruleset verifying audit rows, sim id uniqueness, timestamp ordering."""
    rs = _multi_ruleset()
    guard = SafeApplyGuard()
    html_map = {"file1": HTML}
    payload = {"resources": {"ranking": {}, "players": {}}}
    conn = sqlite3.connect(":memory:")

    sim1 = guard.simulate(rs, html_map, payload)
    assert sim1.passed and sim1.adapter_rows == {"ranking": 2, "players": 2}
    res1 = guard.apply(sim1.sim_id, rs, html_map, payload, conn)  # type: ignore[arg-type]
    assert res1.applied and res1.rows_by_resource == sim1.adapter_rows
    cur = conn.execute(
        "SELECT sim_id, resource, row_count, applied_at FROM rule_apply_audit ORDER BY id"
    )
    audit_rows_1 = cur.fetchall()
    assert len(audit_rows_1) == 2  # two resources
    assert {r[1] for r in audit_rows_1} == {"ranking", "players"}
    assert {r[2] for r in audit_rows_1} == {2}
    sim_ids = {r[0] for r in audit_rows_1}
    assert sim_ids == {sim1.sim_id}
    ts1 = [r[3] for r in audit_rows_1]
    # timestamps exist (string in sqlite default) and are identical or ordered (allow equality due to same second)
    assert all(ts1)

    # Second simulation (sleep to ensure potential timestamp difference)
    time.sleep(0.01)
    sim2 = guard.simulate(rs, html_map, payload)
    assert sim2.sim_id != sim1.sim_id
    res2 = guard.apply(sim2.sim_id, rs, html_map, payload, conn)  # type: ignore[arg-type]
    assert res2.applied
    cur2 = conn.execute(
        "SELECT sim_id, resource, row_count, applied_at FROM rule_apply_audit ORDER BY id"
    )
    all_rows = cur2.fetchall()
    assert len(all_rows) == 4  # two resources * two applies
    # Group counts by sim id
    from collections import defaultdict

    grouped = defaultdict(list)
    for row in all_rows:
        grouped[row[0]].append(row)
    assert set(grouped.keys()) == {sim1.sim_id, sim2.sim_id}
    for gid, entries in grouped.items():
        assert len(entries) == 2
        assert {e[1] for e in entries} == {"ranking", "players"}
        assert {e[2] for e in entries} == {2}
    # Timestamp ordering: last entry timestamp >= first entry timestamp lexicographically
    assert all(all_rows[i + 1][3] >= all_rows[i][3] for i in range(len(all_rows) - 1))


def test_apply_unknown_sim_id_raises():
    rs = _multi_ruleset()
    guard = SafeApplyGuard()
    conn = sqlite3.connect(":memory:")
    try:
        guard.apply(9999, rs, {"f": HTML}, {"resources": {}}, conn)  # type: ignore[arg-type]
        assert False, "Expected ValueError for unknown sim id"
    except ValueError as e:  # expected path
        assert "Unknown simulation id" in str(e)
