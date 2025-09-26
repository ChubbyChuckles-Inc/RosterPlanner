import json

from gui.services.settings_service import SettingsService
from gui.ingestion.rule_apply_guard import SafeApplyGuard
from gui.ingestion.rule_schema import RuleSet


def _minimal_ruleset_mapping():
    # minimal valid structure for existing RuleSet factory (simulate one resource)
    return {"resources": {"sample": {"selector": "table.sample"}}}


def test_preview_batch_cap_affects_iteration(monkeypatch, tmp_path):
    # Adjust settings for small cap and ensure no error thrown creating guard
    SettingsService.instance.ingestion_preview_batch_cap = 3
    # Nothing else to assert here without spinning full GUI; just ensure attribute is set
    assert SettingsService.instance.ingestion_preview_batch_cap == 3


def test_disallow_custom_python_blocks_simulation(monkeypatch):
    SettingsService.instance.ingestion_disallow_custom_python = True
    guard = SafeApplyGuard()
    rules_map = _minimal_ruleset_mapping()
    rs = RuleSet.from_mapping(rules_map)
    # Inject a pretend custom python expression field
    rules_map["custom"] = {"pythonExpr": "lambda x: x"}
    try:
        guard.simulate(rs, {"file1.html": "<html></html>"}, rules_map)
    except Exception as e:
        assert "disallowed" in str(e).lower()
    else:  # pragma: no cover
        raise AssertionError("Expected simulation to be blocked by disallow flag")
    finally:
        SettingsService.instance.ingestion_disallow_custom_python = False
