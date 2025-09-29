import os

import pytest

from gui.ingestion.macro_shortcuts import (
    MacroShortcutTemplate,
    clear_test_store,
    extract_templates_from_ruleset,
    load_templates,
    save_templates,
)
from gui.ingestion.rule_schema import RuleSet


@pytest.fixture(autouse=True)
def _macro_shortcuts_test_mode(monkeypatch):
    monkeypatch.setenv("RP_TEST_MODE", "1")
    clear_test_store()
    yield
    clear_test_store()


def test_template_summary_and_snippet():
    template = MacroShortcutTemplate(
        name="CleanNumber",
        chain=[{"kind": "trim"}, {"kind": "to_number"}],
        sequence="Ctrl+Alt+1",
    )
    assert template.summary() == "trim → to_number"
    snippet = template.render_snippet(indent="  ")
    assert "trim" in snippet and "to_number" in snippet


def test_save_and_load_round_trip():
    templates = [
        MacroShortcutTemplate(
            name="NormalizeName",
            chain=[{"kind": "collapse_ws"}],
            sequence="Ctrl+Alt+N",
            source="custom",
        ),
        MacroShortcutTemplate(
            name="ParseDate",
            chain=[{"kind": "parse_date", "formats": ["%d.%m.%Y", "%Y-%m-%d"]}],
            sequence="Ctrl+Alt+D",
            source="custom",
        ),
    ]
    save_templates(templates)
    loaded = load_templates()
    assert loaded == templates


def test_extract_templates_from_ruleset():
    payload = {
        "transform_macros": {
            "CleanNumber": ["trim", {"kind": "to_number"}],
            "NormalizeName": [{"kind": "collapse_ws"}],
        },
        "resources": {},
    }
    ruleset = RuleSet.from_mapping(payload)
    templates = extract_templates_from_ruleset(ruleset)
    names = {tpl.name for tpl in templates}
    assert names == {"CleanNumber", "NormalizeName"}
    clean_chain = next(tpl.chain for tpl in templates if tpl.name == "CleanNumber")
    assert clean_chain[0]["kind"] == "trim"
    assert clean_chain[1]["kind"] == "to_number"
