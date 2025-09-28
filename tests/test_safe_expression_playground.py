import pytest

from gui.ingestion.safe_expression_playground import (
    build_expr_snippet,
    categorize_value,
    evaluate_expression_playground,
    parse_sample_input,
)


def test_parse_sample_input_auto_json():
    payload = parse_sample_input('{"score": 7}', mode="auto")
    assert payload.value == {"score": 7}
    assert payload.category == "json-object"
    assert "score" in payload.preview


def test_parse_sample_input_force_json_failure():
    with pytest.raises(ValueError):
        parse_sample_input("not json", mode="json")


def test_evaluate_expression_success():
    result = evaluate_expression_playground("len(value)", "[1, 2, 3]", sample_mode="json")
    assert result.ok is True
    assert result.issues == []
    assert result.result_value == 3
    assert result.result_category == "number"
    assert result.snippet == '{"kind": "expr", "code": "len(value)"}'


def test_evaluate_expression_lint_failure():
    result = evaluate_expression_playground("value.__class__", "{}", sample_mode="json")
    assert result.ok is False
    assert result.issues
    assert any(issue.category == "attribute_access" for issue in result.issues)
    assert result.evaluation_error is None


def test_evaluate_expression_runtime_error():
    result = evaluate_expression_playground("value / 0", "2", sample_mode="json")
    assert result.ok is False
    assert result.issues == []
    assert result.evaluation_error


def test_build_expr_snippet_roundtrip():
    snippet = build_expr_snippet("value.strip()")
    assert snippet == '{"kind": "expr", "code": "value.strip()"}'


def test_categorize_value_dict():
    assert categorize_value({"a": 1}) == "object"
