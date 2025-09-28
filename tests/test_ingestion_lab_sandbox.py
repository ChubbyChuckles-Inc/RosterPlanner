import os
import json
import pytest

# Ensure headless / deterministic test environment
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("RP_TEST_MODE", "1")

from PyQt6.QtWidgets import QApplication  # noqa: E402
from gui.views.ingestion_lab.panel import IngestionLabPanel  # noqa: E402


@pytest.fixture(scope="module")
def app_instance():
    app = QApplication.instance()
    if app is None:  # pragma: no cover - safeguard
        app = QApplication([])
    return app


@pytest.fixture()
def panel(app_instance):  # noqa: ANN001
    return IngestionLabPanel(base_dir="data")


@pytest.fixture()
def rules_builder():
    """Helper to build minimal rule sets without repetition.

    Usage:
        rules_builder(list_resource={...}) -> returns JSON string for editor
    Accepts keyword args mapping resource name -> spec mapping (without wrapping version/resources).
    """

    def _build(**resources):  # noqa: ANN001
        payload = {"version": 1, "resources": resources}
        return json.dumps(payload)

    return _build


def test_sandbox_list_rule_happy_path(panel, rules_builder):  # noqa: ANN001
    rules_json = rules_builder(
        players={
            "kind": "list",
            "selector": "div.root",
            "item_selector": "span.item",
            "fields": {
                "name": {"selector": "span"},
                "score": {"selector": "span.score", "transforms": ["to_number"]},
            },
        }
    )
    panel.rule_editor.setPlainText(rules_json)
    fragment = (
        "<div class='root'>"
        "<span class='item'><span>Alice</span><span class='score'>10</span></span>"
        "<span class='item'><span>Bob</span><span class='score'>20</span></span>"
        "</div>"
    )
    panel.sandbox_input.setPlainText(fragment)
    # Ensure transforms unchecked initially
    panel.chk_sandbox_transforms.setChecked(False)
    panel._on_sandbox_parse_clicked()
    out = panel.sandbox_output.toPlainText()
    assert "- players (list) records=2" in out
    assert "rec[0]:" in out
    # Without transforms applied score should be a string representation
    assert "'score': '10'" in out


def test_sandbox_transform_application_flag(panel, rules_builder):  # noqa: ANN001
    rules_json = rules_builder(
        players={
            "kind": "list",
            "selector": "div.root",
            "item_selector": "span.item",
            "fields": {
                "name": {"selector": "span"},
                "score": {"selector": "span.score", "transforms": ["to_number"]},
            },
        }
    )
    panel.rule_editor.setPlainText(rules_json)
    fragment = (
        "<div class='root'>"
        "<span class='item'><span>Alice</span><span class='score'>10</span></span>"
        "<span class='item'><span>Bob</span><span class='score'>20</span></span>"
        "</div>"
    )
    panel.sandbox_input.setPlainText(fragment)
    # Enable transforms and parse
    panel.chk_sandbox_transforms.setChecked(True)
    panel._on_sandbox_parse_clicked()
    out = panel.sandbox_output.toPlainText()
    # With transforms, score values should be numeric (no quotes)
    assert "'score': 10" in out
    assert "'score': '10'" not in out


def test_sandbox_table_rule_happy_path(panel, rules_builder):  # noqa: ANN001
    rules_json = rules_builder(
        ranking={
            "kind": "table",
            "selector": "table.rank",
            "columns": ["col1", "col2"],
        }
    )
    panel.rule_editor.setPlainText(rules_json)
    fragment = (
        "<table class='rank'>"
        "<tr><th>H1</th><th>H2</th></tr>"
        "<tr><td>A</td><td>B</td></tr>"
        "<tr><td>C</td><td>D</td></tr>"
        "</table>"
    )
    panel.sandbox_input.setPlainText(fragment)
    panel._on_sandbox_parse_clicked()
    out = panel.sandbox_output.toPlainText()
    assert "- ranking (table) records=2" in out
    assert "{'col1': 'A', 'col2': 'B'}" in out


def test_sandbox_empty_fragment_no_op(panel, rules_builder):  # noqa: ANN001
    panel.rule_editor.setPlainText(rules_builder())
    panel.sandbox_input.setPlainText("")
    panel._on_sandbox_parse_clicked()
    out = panel.sandbox_output.toPlainText()
    assert out.strip() == "(No fragment provided)"


def test_sandbox_warning_and_log_capture(panel, rules_builder):  # noqa: ANN001
    # Use a list rule whose selector matches but whose field selector does not, producing warnings.
    rules_json = rules_builder(
        players={
            "kind": "list",
            "selector": "div.root",
            "item_selector": "span.item",
            "fields": {"name": {"selector": ".does-not-exist"}},
        }
    )
    panel.rule_editor.setPlainText(rules_json)
    fragment = (
        "<div class='root'>"
        "<span class='item'><span>Alice</span></span>"
        "<span class='item'><span>Bob</span></span>"
        "</div>"
    )
    panel.sandbox_input.setPlainText(fragment)
    panel._on_sandbox_parse_clicked()
    out = panel.sandbox_output.toPlainText()
    # Warning should note list selector matched items but field empty -> still no records due to empties
    assert "warnings=" in out
    # The log should contain the parse summary line we append.
    log_text = panel.log_area.toPlainText()
    assert "Sandbox parsed fragment" in log_text
    # Ensure total records reported equals 0
    assert "total_records=0" in log_text
