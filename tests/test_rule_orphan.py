from gui.ingestion.rule_schema import RuleSet
from gui.ingestion.rule_orphan import compute_orphan_fields


def _ruleset():
    payload = {
        "version": 1,
        "resources": {
            "players": {
                "kind": "list",
                "selector": "ul.p",
                "item_selector": "li",
                "fields": {"name": {"selector": "span.n"}, "rank": {"selector": "span.r"}},
            },
            "ranking": {"kind": "table", "selector": "table.r", "columns": ["team", "pts"]},
        },
    }
    return RuleSet.from_mapping(payload)


def test_orphan_fields():
    rs = _ruleset()
    # Mapping intentionally omits 'rank' and 'pts'
    mapping = {"players": {"name": "player_name"}, "ranking": {"team": "team_name"}}
    orphans = compute_orphan_fields(rs, mapping)
    orphan_keys = {(o.resource, o.field) for o in orphans}
    assert ("players", "rank") in orphan_keys
    assert ("ranking", "pts") in orphan_keys
