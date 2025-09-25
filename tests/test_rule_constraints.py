from gui.ingestion.rule_schema import RuleSet
from gui.ingestion.rule_constraints import simulate_constraints


def _rules():
    return RuleSet.from_mapping(
        {
            "resources": {
                "teams": {"kind": "table", "selector": "table.teams", "columns": ["id", "name"]},
                "players": {"kind": "table", "selector": "table.players", "columns": ["id", "team_id", "name"]},
            }
        }
    )


def test_constraint_simulation_duplicates_and_orphans():
    rs = _rules()
    samples = {
        "teams": [
            {"id": 1, "name": "Alpha"},
            {"id": 1, "name": "Alpha Duplicate"},  # duplicate id
        ],
        "players": [
            {"id": 10, "team_id": 1, "name": "P1"},  # valid
            {"id": 11, "team_id": 999, "name": "P2"},  # orphan fk
        ],
    }
    result = simulate_constraints(rs, samples)
    kinds = sorted(i.kind for i in result.issues)
    assert kinds == ["fk_orphan", "unique_violation"]
    # Validate messages contain helpful context
    msgs = "\n".join(i.message for i in result.issues)
    assert "Duplicate value" in msgs and "no parent" in msgs


def test_constraint_simulation_clean_case():
    rs = _rules()
    samples = {
        "teams": [
            {"id": 1, "name": "Alpha"},
            {"id": 2, "name": "Beta"},
        ],
        "players": [
            {"id": 10, "team_id": 1, "name": "P1"},
            {"id": 11, "team_id": 2, "name": "P2"},
        ],
    }
    result = simulate_constraints(rs, samples)
    assert not result.issues
