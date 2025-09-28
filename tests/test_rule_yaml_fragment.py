import pytest

from gui.ingestion.rule_yaml_fragment import (
    FragmentError,
    apply_fragment,
    clean_fragment_text,
    generate_placeholders,
    load_rules,
    parse_fragment_yaml,
    prepare_insert_snippet,
    resource_fragment_yaml,
)


def test_parse_fragment_with_named_resource():
    text = "team:\n" "  kind: list\n" "  selector: '.row'\n"
    name, spec = parse_fragment_yaml(text, "ignored")
    assert name == "team"
    assert spec["kind"] == "list"
    assert spec["selector"] == ".row"


def test_parse_fragment_direct_spec_uses_fallback():
    text = "kind: table\n" "selector: '.table'\n"
    name, spec = parse_fragment_yaml(text, "results")
    assert name == "results"
    assert spec["kind"] == "table"


def test_apply_fragment_updates_and_renames_resource():
    rules = {"resources": {"old": {"kind": "list", "selector": ".row"}}}
    fragment = "new:\n" "  kind: list\n" "  selector: '.row'\n"
    updated = apply_fragment(rules, "old", fragment)
    assert "old" not in updated["resources"]
    assert "new" in updated["resources"]


def test_resource_fragment_yaml_roundtrip():
    spec = {"kind": "table", "selector": "table"}
    yaml_text = resource_fragment_yaml("scores", spec)
    name, parsed_spec = parse_fragment_yaml(yaml_text, "scores")
    assert name == "scores"
    assert parsed_spec == spec


def test_generate_placeholders_for_list_resource():
    spec = {"kind": "list"}
    placeholders = generate_placeholders(spec)
    labels = [p.display for p in placeholders]
    assert 'selector: ""' in labels
    assert 'item_selector: ""' in labels


def test_prepare_insert_snippet_injects_fields_block_when_missing():
    spec = generate_placeholders({"kind": "list"})
    fields_spec = next(p for p in spec if p.path[0] == "fields")
    snippet = prepare_insert_snippet(fields_spec, "kind: list\n")
    assert snippet.startswith("fields:")
    assert snippet.endswith("\n")


def test_clean_fragment_text_strips_ghost_markers():
    frag = "#? ghost line\nkey: value"
    assert clean_fragment_text(frag) == "key: value\n"


def test_load_rules_bad_json_raises_fragment_error():
    with pytest.raises(FragmentError):
        load_rules("{invalid")
