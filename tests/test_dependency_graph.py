import json
from gui.ingestion.dependency_graph import build_dependency_graph, topological_order

def sample_rules():
    return {
        "version": 1,
        "resources": {
            "ranking_table": {
                "kind": "table",
                "selector": "table.ranking",
                "columns": ["team", "points", "diff"],
            },
            "player_list": {
                "kind": "list",
                "selector": "div.roster",
                "item_selector": "div.player",
                "fields": {
                    "name": {"selector": ".name"},
                    "live_pz": {"selector": ".lpz"},
                    "norm_lpz": {"selector": ".lpz", "transforms": [{"kind": "expr", "code": "live_pz - diff"}]},
                },
            },
        },
        "derived": {
            "ratio": "points / diff",
        },
    }


def test_dependency_graph_build():
    adj, rev = build_dependency_graph(sample_rules())
    # ratio depends on points & diff
    assert "ratio" in rev and rev["ratio"] == {"points", "diff"}
    # norm_lpz depends on live_pz and diff (diff from table)
    assert "norm_lpz" in rev and "live_pz" in rev["norm_lpz"]


def test_topological_order_contains_all():
    adj, _ = build_dependency_graph(sample_rules())
    order = topological_order(adj)
    for node in adj.keys():
        assert node in order


def test_cycle_detection():
    cyc = sample_rules()
    cyc["derived"]["points"] = "ratio"  # create backward edge: ratio -> points already? ratio = points / diff => points -> ratio and ratio -> points
    try:
        build_dependency_graph(cyc)
    except ValueError as e:
        assert "Cycle" in str(e)
    else:
        assert False, "Expected cycle ValueError"
