from gui.ingestion.rule_schema import RuleSet
from gui.ingestion.rule_sandbox import build_sandbox_schema, apply_sandbox_schema
from gui.ingestion.rule_mapping import FieldType


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
                        "points": {
                            "selector": ".pts",
                            "transforms": ["trim", {"kind": "to_number"}],
                        },
                        "joined": {
                            "selector": ".joined",
                            "transforms": [{"kind": "parse_date", "formats": ["%Y-%m-%d"]}],
                        },
                    },
                },
                "ranking_table": {
                    "kind": "table",
                    "selector": "table.ranking",
                    "columns": [
                        "team",
                        "points",
                    ],  # columns default STRING; sandbox test will coerce manually
                },
            },
        }
    )


def test_build_sandbox_schema_default():
    rs = build_rules()
    schema = build_sandbox_schema(rs)
    ddl = schema.ddl()
    # Expect two tables
    assert any("CREATE TABLE sandbox_team_roster" in d for d in ddl)
    assert any("CREATE TABLE sandbox_ranking_table" in d for d in ddl)
    roster_sql = next(d for d in ddl if "sandbox_team_roster" in d)
    assert "name TEXT" in roster_sql and "points REAL" in roster_sql and "joined TEXT" in roster_sql


def test_build_sandbox_schema_overrides():
    rs = build_rules()
    schema = build_sandbox_schema(rs, overrides={("team_roster", "name"): FieldType.NUMBER})
    roster_sql = next(d for d in schema.ddl() if "sandbox_team_roster" in d)
    # overridden name -> REAL
    assert "name REAL" in roster_sql


def test_apply_sandbox_schema():
    rs = build_rules()
    # Provide override to ensure numeric storage for points
    schema = build_sandbox_schema(rs, overrides={("ranking_table", "points"): FieldType.NUMBER})
    conn = apply_sandbox_schema(schema)
    cur = conn.cursor()
    # Insert a row into one table to ensure it exists
    cur.execute("INSERT INTO sandbox_ranking_table (team, points) VALUES (?, ?)", ("X", 5))
    conn.commit()
    cur.execute("SELECT team, points FROM sandbox_ranking_table")
    row = cur.fetchone()
    assert row == ("X", 5)
