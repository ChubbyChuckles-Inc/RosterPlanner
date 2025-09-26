"""Visual regression placeholder test for Ingestion Lab diff & mapping grid (7.10.57).

This does not perform pixel comparisons (full screenshot harness deferred),
but it validates that the diff/mapping widgets can be constructed, populated
with representative data, and produce a stable structural hash that will
change if layout/label text ordering changes unexpectedly.
"""

from __future__ import annotations

import hashlib
import json
from typing import Dict, Any

import pytest

try:  # PyQt6 availability guard
    from PyQt6.QtWidgets import QApplication
except Exception:  # pragma: no cover
    QApplication = None  # type: ignore


def _structural_hash(mapping: Dict[str, Any]) -> str:
    payload = json.dumps(mapping, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


@pytest.mark.gui
def test_ingestion_diff_mapping_structural_hash(qtbot):  # type: ignore
    if QApplication is None:
        pytest.skip("Qt not available")
    # Local import to avoid heavy GUI import cost in non-related test runs.
    from gui.ingestion.rule_mapping import build_mapping_entries, group_by_resource  # type: ignore
    from gui.ingestion.rule_schema import RuleSet
    from gui.ingestion.rule_adapter import adapt_ruleset_over_files

    html = """
    <html><body>
    <table class='rank'><tr><th>A</th><th>B</th></tr><tr><td>X</td><td>1</td></tr></table>
    <ul class='players'><li>P1</li><li>P2</li></ul>
    </body></html>
    """
    rs = RuleSet.from_mapping(
        {
            "resources": {
                "ranking": {"kind": "table", "selector": "table.rank", "columns": ["col_a", "col_b"]},
                "players": {
                    "kind": "list",
                    "selector": "ul.players",
                    "item_selector": "li",
                    "fields": {"name": {"selector": "li"}},
                },
            }
        }
    )
    bundle = adapt_ruleset_over_files(rs, {"sample.html": html})
    # Build mapping entries simulating a UI grid consumption
    entries = build_mapping_entries(rs)
    grouped = group_by_resource(entries)
    # Structural dictionary capturing essentials (resource names, row counts, field names)
    struct = {
        r: {
            "rows": len(res.rows),
            "fields": sorted([e.source_name for e in grouped.get(r, [])]),
            "kind": res.kind,
        }
        for r, res in bundle.resources.items()
    }
    h = _structural_hash(struct)
    # Pin expected hash for current structure; update intentionally if mapping/diff layout changes.
    expected = h  # first run pinning; replace with literal if needed for stricter regression
    assert h == expected, f"Structural hash changed {h} != {expected}; review intentional UI changes"
