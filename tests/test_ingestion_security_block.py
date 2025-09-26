"""Security tests for disallowed python / expression usage (Milestone 7.10.58).

These tests exercise two complementary security layers:
 1. Settings flag ingestion_disallow_custom_python blocking any attempt to run
    custom python expression style payload fragments (legacy heuristic: keys containing
    'python').
 2. Extended heuristic (added in this milestone) scanning raw rule payload for
    TransformSpec entries with kind=='expr' (expression transforms) and blocking
    simulation when the settings flag is enabled.

We also provide a control test showing that with the flag disabled a ruleset
containing expression transforms parses & simulates successfully (allow_expressions=True).

The tests purposely avoid deep HTML extraction (simple minimal HTML) focusing
on the guard behaviour.
"""

from __future__ import annotations

import pytest

from gui.services.settings_service import SettingsService
from gui.ingestion.rule_apply_guard import SafeApplyGuard
from gui.ingestion.rule_schema import RuleSet


MIN_HTML = {
    "file.html": "<html><body><div class='row'><span class='val'>5</span></div></body></html>"
}


def _base_rules_payload():
    return {
        "allow_expressions": True,
        "resources": {
            "sample": {
                "kind": "list",
                "selector": "div.row",
                "item_selector": "div.row",
                "fields": {
                    "val": {
                        "selector": ".val",
                        # transforms injected per test
                        "transforms": [],
                    }
                },
            }
        },
    }


def test_disallow_flag_blocks_legacy_python_key():
    SettingsService.instance.ingestion_disallow_custom_python = True
    guard = SafeApplyGuard()
    payload = _base_rules_payload()
    # Inject a legacy style custom python block at top level (previous heuristic)
    payload["custom"] = {"pythonExpr": "lambda x: x"}
    rs = RuleSet.from_mapping(payload)
    with pytest.raises(Exception) as exc:
        guard.simulate(rs, MIN_HTML, payload)
    assert "disallow" in str(exc.value).lower()
    SettingsService.instance.ingestion_disallow_custom_python = False


def test_disallow_flag_blocks_expr_transform():
    SettingsService.instance.ingestion_disallow_custom_python = True
    guard = SafeApplyGuard()
    payload = _base_rules_payload()
    # Add an expression transform (new heuristic path)
    payload["resources"]["sample"]["fields"]["val"]["transforms"].append(
        {"kind": "expr", "code": "value + '1'"}
    )
    rs = RuleSet.from_mapping(payload)
    with pytest.raises(Exception) as exc:
        guard.simulate(rs, MIN_HTML, payload)
    assert "expr" in str(exc.value).lower() or "custom python" in str(exc.value).lower()
    SettingsService.instance.ingestion_disallow_custom_python = False


def test_expr_transform_allowed_when_flag_disabled():
    SettingsService.instance.ingestion_disallow_custom_python = False
    guard = SafeApplyGuard()
    payload = _base_rules_payload()
    payload["resources"]["sample"]["fields"]["val"]["transforms"].append(
        {"kind": "expr", "code": "value + '1'"}
    )
    rs = RuleSet.from_mapping(payload)
    sim = guard.simulate(rs, MIN_HTML, payload)
    assert sim.sim_id == 1
    # either passes (no reasons) or reasons unrelated to security
    assert not [r for r in sim.reasons if "python" in r.lower() or "expr" in r.lower()]
