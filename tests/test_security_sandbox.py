"""Tests for security sandbox static analyzer (Milestone 7.10.41)."""

from __future__ import annotations

from gui.ingestion.security_sandbox import scan_expression, scan_rules_text


def test_scan_expression_allowed_simple():
    issues = scan_expression("a + b * 2", allowed_names={"a", "b"})
    assert issues == []


def test_scan_expression_empty():
    issues = scan_expression("   ")
    assert any(i.category == "empty" for i in issues)


def test_scan_expression_disallowed_call():
    issues = scan_expression("sum(values)")
    # function call should be flagged regardless of name allow list
    assert any(i.category == "function_call" for i in issues)


def test_scan_expression_attribute_and_subscript():
    issues = scan_expression("obj.attr[0]")
    cats = {i.category for i in issues}
    assert "attribute_access" in cats or "subscript" in cats  # both may appear


def test_scan_expression_unknown_name():
    issues = scan_expression("a + b", allowed_names={"a"})
    assert any(i.category == "unknown_name" for i in issues)


def test_scan_rules_text_integration():
    raw = {
        "resources": {
            "team": {
                "fields": {
                    "points": {"selector": ".p"},
                    "diff": {
                        "selector": ".d",
                        "transforms": [{"kind": "expr", "code": "value + 1"}],
                    },
                }
            }
        },
        "derived": {"ratio": "points / diff", "bad": "call()"},
    }
    import json

    report = scan_rules_text(json.dumps(raw))
    assert report.expressions_scanned == 3  # one transform expr + two derived
    # Should have at least one function_call issue for bad derived
    assert any(i.category == "function_call" for i in report.issues)
    # 'ratio' should be ok (no issues tied to field 'ratio')
    assert not [i for i in report.issues if i.field == "ratio"]
