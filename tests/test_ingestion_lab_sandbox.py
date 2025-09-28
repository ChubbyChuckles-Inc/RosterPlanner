import os
import json
import pytest

# Ensure headless / deterministic test environment
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("RP_TEST_MODE", "1")

from PyQt6.QtWidgets import QApplication  # noqa: E402
from gui.views.ingestion_lab_panel import IngestionLabPanel  # noqa: E402


@pytest.fixture(scope="module")
def app_instance():
    app = QApplication.instance()
    if app is None:  # pragma: no cover - safeguard
        app = QApplication([])
    return app


def _make_panel(app_instance):  # noqa: ANN001
    panel = IngestionLabPanel(base_dir="data")
    return panel


def test_sandbox_list_rule_happy_path(app_instance):
    panel = _make_panel(app_instance)
    rules = {
        "version": 1,
        "resources": {
            "players": {
                "kind": "list",
                "selector": "div.root",
                "item_selector": "span.item",
                "fields": {
                    "name": {"selector": "span"},
                    "score": {"selector": "span.score", "transforms": ["to_number"]},
                },
            }
        },
    }
    panel.rule_editor.setPlainText(json.dumps(rules))
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


def test_sandbox_transform_application_flag(app_instance):
    panel = _make_panel(app_instance)
    rules = {
        "version": 1,
        "resources": {
            "players": {
                "kind": "list",
                "selector": "div.root",
                "item_selector": "span.item",
                "fields": {
                    "name": {"selector": "span"},
                    "score": {"selector": "span.score", "transforms": ["to_number"]},
                },
            }
        },
    }
    panel.rule_editor.setPlainText(json.dumps(rules))
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


def test_sandbox_table_rule_happy_path(app_instance):
    panel = _make_panel(app_instance)
    rules = {
        "version": 1,
        "resources": {
            "ranking": {
                "kind": "table",
                "selector": "table.rank",
                "columns": ["col1", "col2"],
            }
        },
    }
    panel.rule_editor.setPlainText(json.dumps(rules))
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


def test_sandbox_empty_fragment_no_op(app_instance):
    panel = _make_panel(app_instance)
    rules = {"version": 1, "resources": {}}
    panel.rule_editor.setPlainText(json.dumps(rules))
    panel.sandbox_input.setPlainText("")
    panel._on_sandbox_parse_clicked()
    out = panel.sandbox_output.toPlainText()
    assert out.strip() == "(No fragment provided)"
