"""Tests for rule export / import utilities (Milestone 7.10.42)."""

from __future__ import annotations

import os
import json
from gui.ingestion.rule_export import export_rules, import_rules


SAMPLE_RULES = {
    "resources": {
        "ranking_table": {
            "kind": "table",
            "selector": "table.ranking",
            "columns": ["team", "points"],
        },
        "team_roster": {
            "kind": "list",
            "selector": "div.roster",
            "item_selector": "div.player",
            "fields": {"name": ".n", "lpz": {"selector": ".p", "transforms": ["trim"]}},
        },
    }
}


def test_export_import_roundtrip(tmp_path):
    path = tmp_path / "rules_export.json"
    out_path = export_rules(json.dumps(SAMPLE_RULES), str(path))
    assert os.path.isfile(out_path)
    loaded = import_rules(out_path)
    data_loaded = json.loads(loaded)
    assert data_loaded["resources"]["ranking_table"]["kind"] == "table"
    assert data_loaded["resources"]["team_roster"]["kind"] == "list"
    # Ensure version injected
    assert isinstance(data_loaded.get("version"), int)


def test_export_rejects_invalid(tmp_path):
    bad = {"resources": {"x": {"kind": "table", "selector": "", "columns": []}}}
    import json as _j
    try:
        export_rules(_j.dumps(bad), str(tmp_path / "bad.json"))
    except ValueError as e:
        assert "Rule validation failed" in str(e)
    else:  # pragma: no cover - we expect failure
        raise AssertionError("Expected ValueError for invalid rules")


def test_import_missing_file(tmp_path):
    try:
        import_rules(str(tmp_path / "missing.json"))
    except ValueError as e:
        assert "does not exist" in str(e)
    else:  # pragma: no cover
        raise AssertionError("Expected missing file error")
