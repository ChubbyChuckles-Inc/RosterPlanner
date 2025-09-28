import json

from gui.ingestion.bulk_edit_dialog import bulk_edit_rules


def test_bulk_edit_add_transform_and_selector_replace():
    rules = {
        "version": 1,
        "resources": {
            "players": {
                "kind": "list",
                "selector": "div.root",
                "item_selector": "span.item",
                "fields": {
                    "name": {"selector": "span.name"},
                    "rating": {"selector": "span.rating"},
                },
            },
            "ranking": {  # table rule should be ignored
                "kind": "table",
                "selector": "table.rank",
                "columns": ["team", "pts"],
            },
        },
    }
    selections = [("players", "name"), ("players", "rating")]
    modified = bulk_edit_rules(
        rules, selections, add_transform="trim", find="span.", replace="div."
    )
    assert modified["resources"]["players"]["fields"]["name"]["selector"] == "div.name"
    assert modified["resources"]["players"]["fields"]["rating"]["selector"] == "div.rating"
    # Transform should have been added to both
    for fname in ["name", "rating"]:
        chain = modified["resources"]["players"]["fields"][fname]["transforms"]
        assert chain == ["trim"]


def test_bulk_edit_idempotent_transform():
    rules = {
        "version": 1,
        "resources": {
            "players": {
                "kind": "list",
                "selector": "div.root",
                "item_selector": "span.item",
                "fields": {
                    "name": {"selector": "span.name", "transforms": ["trim"]},
                },
            }
        },
    }
    selections = [("players", "name")]
    modified = bulk_edit_rules(rules, selections, add_transform="trim")
    # Should not duplicate transform
    chain = modified["resources"]["players"]["fields"]["name"]["transforms"]
    assert chain == ["trim"]


def test_bulk_edit_unsupported_transform_ignored():
    rules = {
        "version": 1,
        "resources": {
            "players": {
                "kind": "list",
                "selector": "div.root",
                "item_selector": "span.item",
                "fields": {"name": {"selector": "span.name"}},
            }
        },
    }
    selections = [("players", "name")]
    modified = bulk_edit_rules(rules, selections, add_transform="parse_date")
    # Unsupported transform should not be applied
    assert "transforms" not in modified["resources"]["players"]["fields"]["name"]


def test_bulk_edit_simple_string_field_normalization():
    # Field stored as simple selector string should be normalized to mapping form
    rules = {
        "version": 1,
        "resources": {
            "players": {
                "kind": "list",
                "selector": "div.root",
                "item_selector": "span.item",
                "fields": {"name": "span.name"},
            }
        },
    }
    selections = [("players", "name")]
    modified = bulk_edit_rules(rules, selections, add_transform="trim", find="span", replace="div")
    fmap = modified["resources"]["players"]["fields"]["name"]
    assert isinstance(fmap, dict)
    assert fmap["selector"] == "div.name"
    assert fmap["transforms"] == ["trim"]
