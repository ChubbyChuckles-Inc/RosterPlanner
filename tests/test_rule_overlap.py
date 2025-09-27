from gui.ingestion.rule_schema import RuleSet
from gui.ingestion.rule_overlap import detect_overlaps


def build_ruleset():
    payload = {
        "version": 1,
        "resources": {
            "list_all": {
                "kind": "list",
                "selector": "ul.players",
                "item_selector": "li.item",
                "fields": {"name": ".name"},
            },
            "list_special": {
                "kind": "list",
                "selector": "ul.players",
                "item_selector": "li.item.special",
                "fields": {"name": ".name"},
            },
        },
    }
    return RuleSet.from_mapping(payload)


def test_detect_overlaps_basic():
    rs = build_ruleset()
    html = """
    <html><body>
      <ul class='players'>
        <li class='item'><span class='name'>A</span></li>
        <li class='item special'><span class='name'>B</span></li>
      </ul>
      <ul class='players special'>
        <li class='item special'><span class='name'>C</span></li>
      </ul>
    </body></html>
    """
    overlaps = detect_overlaps(rs, html)
    # Expect exactly one pair
    assert len(overlaps) == 1
    rec = overlaps[0]
    assert {rec.resource_a, rec.resource_b} == {"list_all", "list_special"}
    # list_all has 3 items, list_special 2, overlap 2
    assert rec.overlap == 2
    assert rec.count_a in (2, 3) and rec.count_b in (2, 3)
    # Jaccard should be 2/3 ≈ 0.666666 (rounded in implementation)
    assert abs(rec.jaccard - (2 / 3)) < 1e-6
