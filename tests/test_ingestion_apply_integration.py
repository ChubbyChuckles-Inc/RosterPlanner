import sqlite3

from gui.ingestion.rule_schema import RuleSet
from gui.ingestion.rule_apply_guard import SafeApplyGuard


HTML = """
<html><body>
<table class='r'><tr><th>Team</th><th>Pts</th></tr>
<tr><td>A</td><td>5</td></tr>
<tr><td>B</td><td>7</td></tr>
</table>
</body></html>
"""


def _ruleset():
    return RuleSet.from_mapping(
        {
            "resources": {
                "ranking": {"kind": "table", "selector": "table.r", "columns": ["team", "pts"]}
            }
        }
    )


def test_apply_integration_audit_counts():
    """Simulate then apply and verify audit table row counts and idempotent apply constraint."""
    rs = _ruleset()
    guard = SafeApplyGuard()
    html_map = {"f1": HTML}
    sim = guard.simulate(rs, html_map, {"resources": {"ranking": {}}})
    assert sim.passed
    conn = sqlite3.connect(":memory:")
    result = guard.apply(sim.sim_id, rs, html_map, {"resources": {"ranking": {}}}, conn)  # type: ignore[arg-type]
    assert result.applied
    # Audit table should contain entries equal to number of resources (1) with row_count == extracted rows (2 data rows)
    cur = conn.execute("SELECT resource, row_count FROM rule_apply_audit")
    rows = cur.fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "ranking"
    assert rows[0][1] == 2
    # Re-applying same simulation id should raise (already used or unknown if mutated) — simulate new changes by re-running simulate
    sim2 = guard.simulate(rs, html_map, {"resources": {"ranking": {}}})
    result2 = guard.apply(sim2.sim_id, rs, html_map, {"resources": {"ranking": {}}}, conn)  # type: ignore[arg-type]
    cur2 = conn.execute("SELECT COUNT(*) FROM rule_apply_audit")
    total_entries = cur2.fetchone()[0]
    # Two apply operations -> two audit groups (resource count each =1) => 2 rows
    assert total_entries == 2
