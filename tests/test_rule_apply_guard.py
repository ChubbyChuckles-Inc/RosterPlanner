import sqlite3
from gui.ingestion.rule_schema import RuleSet
from gui.ingestion.rule_apply_guard import SafeApplyGuard

RULES = {
    "version": 1,
    "resources": {
        "players": {
            "kind": "list",
            "selector": "ul.p",
            "item_selector": "li",
            "fields": {"name": {"selector": "span.n"}, "rank": {"selector": "span.r"}},
        }
    },
    "quality_gates": {"players.name": 1.0, "players.rank": 0.5},
}

HTML = {
    "f1": """
    <html><body>
    <ul class='p'>
      <li><span class='n'>Alice</span><span class='r'>1</span></li>
      <li><span class='n'>Bob</span></li>
    </ul>
    </body></html>
    """,
}

def test_safe_apply_guard_simulate_and_apply():
    rs = RuleSet.from_mapping(RULES)
    guard = SafeApplyGuard()
    sim = guard.simulate(rs, HTML, RULES)
    # players.rank gate threshold 0.5 satisfied (1 non-empty / 2 = 0.5)
    assert sim.passed is True
    assert sim.adapter_rows["players"] == 2
    conn = sqlite3.connect(":memory:")
    apply_res = guard.apply(sim.sim_id, rs, HTML, RULES, conn)
    assert apply_res.applied is True
    cur = conn.execute("SELECT resource, row_count FROM rule_apply_audit")
    rows = cur.fetchall()
    assert rows == [("players", 2)]


def test_safe_apply_guard_prevents_failed_apply():
    bad_rules = {
        "version": 1,
        "resources": {
            "players": {
                "kind": "list",
                "selector": "ul.none",  # will match zero
                "item_selector": "li",
                "fields": {"name": {"selector": "span.n"}},
            }
        },
        "quality_gates": {"players.name": 1.0},  # gate references empty resource
    }
    rs = RuleSet.from_mapping(bad_rules)
    guard = SafeApplyGuard()
    sim = guard.simulate(rs, HTML, bad_rules)
    assert sim.passed is False
    conn = sqlite3.connect(":memory:")
    try:
        guard.apply(sim.sim_id, rs, HTML, bad_rules, conn)
    except RuntimeError:
        pass
    else:
        raise AssertionError("Expected RuntimeError for failed simulation")
