import pytest
from gui.design import load_tokens, get_duration_ms, get_easing_curve, parse_cubic_bezier


def test_duration_tokens_exist():
    tokens = load_tokens()
    assert get_duration_ms(tokens, "instant") >= 50  # sanity lower bound
    assert get_duration_ms(tokens, "fast") < get_duration_ms(tokens, "slow")


def test_easing_parse_standard():
    tokens = load_tokens()
    x1, y1, x2, y2 = get_easing_curve(tokens, "standard")
    assert 0 <= x1 <= 1 and 0 <= x2 <= 1
    assert 0 <= y1 <= 1 and 0 <= y2 <= 1


def test_invalid_duration_raises():
    tokens = load_tokens()
    with pytest.raises(KeyError):
        get_duration_ms(tokens, "not-a-token")


def test_invalid_easing_raises():
    tokens = load_tokens()
    with pytest.raises(KeyError):
        get_easing_curve(tokens, "nonexistent-easing")


def test_parse_cubic_bezier_manual():
    x1, y1, x2, y2 = parse_cubic_bezier("cubic-bezier(0.1, 0.2, 0.3, 0.9)")
    assert (x1, y1, x2, y2) == (0.1, 0.2, 0.3, 0.9)


def test_parse_invalid_format():
    with pytest.raises(ValueError):
        parse_cubic_bezier("bezier(0,0,0,0)")
