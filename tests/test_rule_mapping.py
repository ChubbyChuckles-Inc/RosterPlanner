from gui.ingestion.rule_schema import RuleSet
from gui.ingestion.rule_mapping import build_mapping_entries, group_by_resource, FieldType


def build_rules():
    return RuleSet.from_mapping(
        {
            "allow_expressions": True,
            "resources": {
                "team_roster": {
                    "kind": "list",
                    "selector": "div.roster",
                    "item_selector": "div.player",
                    "fields": {
                        "name": {"selector": ".name", "transforms": ["trim"]},
                        "points": {"selector": ".pts", "transforms": ["trim", {"kind": "to_number"}]},
                        "joined": {"selector": ".joined", "transforms": [{"kind": "parse_date", "formats": ["%Y-%m-%d"]}]},
                        "calc": {"selector": ".raw", "transforms": [{"kind": "expr", "code": "len(value)"}]},
                    },
                },
                "ranking_table": {
                    "kind": "table",
                    "selector": "table.ranking",
                    "columns": ["team", "points"],
                },
            }
        }
    )


def test_build_mapping_entries_types():
    rs = build_rules()
    entries = build_mapping_entries(rs)
    by_name = { (e.resource, e.source_name): e for e in entries }
    assert by_name[("team_roster", "points")].inferred_type == FieldType.NUMBER
    assert by_name[("team_roster", "joined")].inferred_type == FieldType.DATE
    assert by_name[("team_roster", "name")].inferred_type == FieldType.STRING
    # expr alone does not change type
    assert by_name[("team_roster", "calc")].inferred_type == FieldType.STRING
    assert by_name[("ranking_table", "team")].is_table


def test_group_by_resource():
    rs = build_rules()
    entries = build_mapping_entries(rs)
    grouped = group_by_resource(entries)
    assert set(grouped.keys()) == {"team_roster", "ranking_table"}
    assert len(grouped["team_roster"]) == 4
    assert len(grouped["ranking_table"]) == 2
