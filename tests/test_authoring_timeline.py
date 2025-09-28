import json

import pytest

from gui.views.ingestion_lab.timeline import AuthoringTimelineModel


def _pretty(data):
    return json.dumps(data, indent=2, sort_keys=True)


def test_timeline_detects_added_field():
    baseline = {
        "resources": {
            "team": {
                "kind": "list",
                "selector": ".row",
                "fields": {
                    "name": {"selector": ".name"},
                },
            }
        }
    }
    updated = {
        "resources": {
            "team": {
                "kind": "list",
                "selector": ".row",
                "fields": {
                    "name": {"selector": ".name"},
                    "points": {"selector": ".points"},
                },
            }
        }
    }
    model = AuthoringTimelineModel()
    model.reset(_pretty(baseline))
    entry = model.ingest(_pretty(updated))
    assert entry is not None
    assert "Added field 'points'" in entry.summary
    assert any("points" in detail for detail in entry.details)
    assert '"points"' in entry.diff


def test_timeline_detects_selector_change():
    baseline = {
        "resources": {
            "table": {
                "kind": "table",
                "selector": "table.standings",
                "columns": ["rank", "team"],
            }
        }
    }
    updated = {
        "resources": {
            "table": {
                "kind": "table",
                "selector": "table#league",
                "columns": ["rank", "team"],
            }
        }
    }
    model = AuthoringTimelineModel()
    model.reset(_pretty(baseline))
    entry = model.ingest(_pretty(updated))
    assert entry is not None
    assert "Updated selector" in entry.summary
    assert "table" in entry.summary
    assert "table" in entry.diff


def test_timeline_ignores_invalid_json_then_captures_next_change():
    model = AuthoringTimelineModel()
    model.reset("{}")
    assert model.ingest('{"resources": ') is None
    assert model.last_parse_error is not None
    entry = model.ingest(_pretty({"resources": {"a": {"kind": "list"}}}))
    assert entry is not None
    assert "Added resource 'a'" in entry.summary
    next_entry = model.ingest(_pretty({"resources": {"a": {"kind": "list", "selector": ".row"}}}))
    assert next_entry is not None
    assert "Updated selector" in next_entry.summary


def test_timeline_strips_visual_builder_block():
    text = """{\n  \"resources\": {}\n}\n# --- Visual Builder Draft BEGIN ---\n# Visual Builder Draft Resources\n{\n  \"resources\": {\n    \"draft\": {\"kind\": \"list\"}\n  }\n}\n# --- Visual Builder Draft END ---\n"""
    model = AuthoringTimelineModel()
    model.reset(text)
    mapping = model.current_mapping
    assert mapping == {"resources": {}}
    entry = model.ingest(_pretty({"resources": {"draft": {"kind": "list"}}}))
    assert entry is not None
    assert "Added resource 'draft'" in entry.summary


@pytest.mark.parametrize(
    "max_entries",
    [3],
)
def test_timeline_max_entries(max_entries):
    model = AuthoringTimelineModel(max_entries=max_entries)
    model.reset("{}")
    for idx in range(max_entries + 2):
        payload = {"resources": {f"r{idx}": {"kind": "list"}}}
        entry = model.ingest(_pretty(payload))
        if entry is None:
            continue
    assert len(model.entries()) <= max_entries
