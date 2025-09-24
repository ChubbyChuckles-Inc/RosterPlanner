from gui.design.loader import load_tokens
from gui.design.color_picker_utils import (
    hex_to_rgb,
    rgb_to_hex,
    color_distance,
    nearest_color_token,
)


def test_hex_roundtrip():
    assert hex_to_rgb("#3d8bfd") == (61, 139, 253)
    assert rgb_to_hex((61, 139, 253)) == "#3d8bfd"


def test_color_distance_ordering():
    a = (0, 0, 0)
    b = (1, 1, 1)
    c = (10, 10, 10)
    assert color_distance(a, b) < color_distance(a, c)


def test_nearest_token_primary_accent():
    tokens = load_tokens()
    key, token_hex, dist = nearest_color_token("#3d8bfd", tokens)
    assert key.endswith("accent.primary")
    assert token_hex.lower() == "#3d8bfd"
    assert dist == 0


def test_nearest_token_fuzzy_match():
    tokens = load_tokens()
    # Slight variation of accent.primary
    key, token_hex, dist = nearest_color_token("#3d90fd", tokens)
    assert key.endswith("accent.primary")  # still maps to primary accent
    assert dist > 0
