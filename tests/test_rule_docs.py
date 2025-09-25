from gui.ingestion.rule_schema import RuleSet
from gui.ingestion.rule_docs import generate_global_docs, generate_resource_docs


def build_rules():
    return RuleSet.from_mapping(
        {
            "allow_expressions": True,
            "resources": {
                "base_table": {"kind": "table", "selector": "table.base", "columns": ["a", "b"]},
                "child_table": {"kind": "table", "extends": "base_table", "selector": "table.child", "columns": ["a", "b", "c"]},
                "team_roster": {
                    "kind": "list",
                    "selector": "div.roster",
                    "item_selector": "div.player",
                    "fields": {
                        "name": {"selector": ".name", "transforms": ["trim"]},
                        "points": {"selector": ".pts", "transforms": ["trim", {"kind": "to_number"}]},
                        "joined": {"selector": ".joined", "transforms": [{"kind": "parse_date", "formats": ["%Y-%m-%d"]}]},
                        "calc": {"selector": ".raw", "transforms": [{"kind": "expr", "code": "value.strip()"}]},
                    },
                },
            }
        }
    )


def test_generate_global_docs_contains_sections():
    rs = build_rules()
    text = generate_global_docs(rs)
    assert "# Rule Schema Documentation" in text
    assert "### Resources" in text
    assert "child_table" in text
    assert "expr" in text  # expression transform mention


def test_generate_resource_docs_list_rule():
    rs = build_rules()
    txt = generate_resource_docs("team_roster", rs)
    assert "## Resource: team_roster" in txt
    assert "Root Selector:" in txt
    assert "transforms:" in txt
    assert "parse_date(formats=[%Y-%m-%d])" in txt


def test_generate_resource_docs_table_rule():
    rs = build_rules()
    txt = generate_resource_docs("child_table", rs)
    assert "Columns" in txt
    assert "child_table" in txt
    assert "Extends:" in txt
