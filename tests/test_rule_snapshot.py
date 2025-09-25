from gui.ingestion.rule_schema import RuleSet
from gui.ingestion.rule_snapshot import (
    generate_snapshot,
    save_snapshot,
    load_snapshot,
    compare_snapshot,
)


def _ruleset():
    payload = {
        "version": 1,
        "resources": {
            "ranking": {"kind": "table", "selector": "table.r", "columns": ["team", "pts"]},
            "players": {
                "kind": "list",
                "selector": "ul.p",
                "item_selector": "li",
                "fields": {"name": {"selector": "span.n"}},
            },
        },
    }
    return RuleSet.from_mapping(payload)


def test_snapshot_generation_and_persistence(tmp_path):
    rs = _ruleset()
    html_by_file = {
        "file1": """
        <html><body>
        <table class='r'><tr><th>Team</th><th>Pts</th></tr><tr><td>A</td><td>5</td></tr></table>
        <ul class='p'><li><span class='n'>Alice</span></li></ul>
        </body></html>
        """,
        "file2": """
        <html><body>
        <table class='r'><tr><th>Team</th><th>Pts</th></tr><tr><td>B</td><td>7</td></tr></table>
        <ul class='p'><li><span class='n'>Bob</span></li></ul>
        </body></html>
        """,
    }
    capture = generate_snapshot("baseline", rs, html_by_file)
    manifest_path = save_snapshot(capture, str(tmp_path), include_per_file=True)
    assert (tmp_path / "baseline" / "snapshot.json").exists()
    loaded = load_snapshot(str(manifest_path))
    diffs = compare_snapshot(capture, loaded)
    # All difference categories should be empty
    assert all(len(v) == 0 for v in diffs.values())


def test_snapshot_compare_detects_diff(tmp_path):
    rs = _ruleset()
    html_by_file = {
        "file1": "<html><body><table class='r'><tr><th>Team</th><th>Pts</th></tr><tr><td>A</td><td>5</td></tr></table></body></html>"
    }
    capture = generate_snapshot("baseline", rs, html_by_file)
    manifest_path = save_snapshot(capture, str(tmp_path))
    loaded = load_snapshot(str(manifest_path))
    # Mutate loaded aggregated rows to simulate diff
    loaded["aggregated"]["ranking"][0]["team"] = "Changed"  # type: ignore[index]
    diffs = compare_snapshot(capture, loaded)
    assert any("ranking[0]" in d for d in diffs["row_mismatch"]) or diffs["row_mismatch"]
