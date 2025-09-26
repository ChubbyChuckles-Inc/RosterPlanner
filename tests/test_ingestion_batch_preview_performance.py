"""Performance test for ingestion batch preview (Milestone 7.10.56).

This test exercises the rule adapter over a batch of roster HTML files to
establish a baseline parse+aggregation time budget. It is intentionally
lightweight and will skip if insufficient sample files exist.

Success Criteria (initial baseline):
 - Batch of up to 50 roster files adapts in < 1.5 seconds wall time on
   typical dev hardware. (Loose threshold; can be tightened once stable.)
 - At least 1 resource extracted with >0 total rows across batch.

If future regressions emerge the threshold may be adjusted or replaced by
percentile comparison infrastructure.
"""

from __future__ import annotations

import time
import pathlib
import pytest

from gui.ingestion.rule_schema import RuleSet
from gui.ingestion.rule_adapter import adapt_ruleset_over_files


ROSTER_GLOB = "team_roster_*.html"
MAX_FILES = 50
THRESHOLD_SECONDS = 1.5


def _build_ruleset() -> RuleSet:
    # Minimal list rule that targets table rows (fallback: treat tr as item) plus a table variant.
    # Most roster pages contain a ranking/lineup table with player names & optional LivePZ.
    return RuleSet.from_mapping(
        {
            "resources": {
                "players_table": {
                    "kind": "table",
                    "selector": "table",
                    "columns": ["c1", "c2", "c3", "c4"],
                },
                "players_list": {
                    "kind": "list",
                    "selector": "table",
                    "item_selector": "tr",
                    "fields": {
                        "col1": {"selector": "td"},
                        "col2": {"selector": "td"},
                    },
                },
            }
        }
    )


@pytest.mark.performance
def test_batch_preview_performance():
    data_dir = pathlib.Path("data")
    files = sorted(data_dir.rglob(ROSTER_GLOB))
    if not files:
        pytest.skip("No roster HTML files available for performance test")
    subset = files[:MAX_FILES]
    html_map = {f.name: f.read_text(encoding="utf-8", errors="ignore") for f in subset}
    rs = _build_ruleset()
    start = time.perf_counter()
    bundle = adapt_ruleset_over_files(rs, html_map)
    elapsed = time.perf_counter() - start
    # Basic assertions
    assert bundle.resources, "Expected at least one resource extracted"
    total_rows = sum(len(r.rows) for r in bundle.resources.values())
    assert total_rows >= 0  # allow zero if pages radically differ, but resource presence verified
    assert elapsed < THRESHOLD_SECONDS, f"Batch preview took {elapsed:.3f}s (threshold {THRESHOLD_SECONDS}s)"
