import pytest

from gui.ingestion.rule_schema import TransformSpec
from gui.ingestion.rule_transforms import apply_transform_chain, TransformExecutionError


def test_basic_trim_and_collapse():
    specs = [TransformSpec(kind="trim"), TransformSpec(kind="collapse_ws")]
    result = apply_transform_chain("  a   b  ", specs, allow_expressions=False)
    assert result == "a b"


def test_number_parsing():
    specs = [TransformSpec(kind="to_number")]
    assert apply_transform_chain("1 234", specs, allow_expressions=False) == 1234
    assert apply_transform_chain("1,234", specs, allow_expressions=False) == 1234
    assert apply_transform_chain("1,234.5", specs, allow_expressions=False) == 1234.5
    assert (
        apply_transform_chain("12,34", specs, allow_expressions=False) == 1234
    )  # thousands style fallback


def test_parse_date_first_matching():
    specs = [TransformSpec(kind="parse_date", formats=["%d.%m.%Y", "%Y-%m-%d"])]
    assert apply_transform_chain("07.09.2025", specs, allow_expressions=False) == "2025-09-07"
    assert apply_transform_chain("2025-09-07", specs, allow_expressions=False) == "2025-09-07"


def test_parse_date_failure():
    specs = [TransformSpec(kind="parse_date", formats=["%d.%m.%Y"])]
    with pytest.raises(TransformExecutionError):
        apply_transform_chain("2025/09/07", specs, allow_expressions=False)


def test_expression_disabled_by_flag():
    specs = [TransformSpec(kind="expr", code="value + 1")]
    with pytest.raises(TransformExecutionError):
        apply_transform_chain(1, specs, allow_expressions=False)


def test_expression_enabled():
    specs = [TransformSpec(kind="expr", code="value + 1")]
    assert apply_transform_chain(1, specs, allow_expressions=True) == 2


def test_expression_forbidden_tokens():
    specs = [TransformSpec(kind="expr", code="__import__('os').system('echo hi')")]
    with pytest.raises(TransformExecutionError):
        apply_transform_chain(1, specs, allow_expressions=True)
