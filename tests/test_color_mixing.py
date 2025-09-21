import pytest

from src.gui.design import color_mixing as cm


def test_parse_and_roundtrip_variants():
    assert cm.parse_hex("#fff") == (255, 255, 255, 255)
    assert cm.parse_hex("#000") == (0, 0, 0, 255)
    assert cm.parse_hex("#ff0000") == (255, 0, 0, 255)
    assert cm.parse_hex("#ff000080") == (255, 0, 0, 128)
    # roundtrip
    r, g, b, a = cm.parse_hex("#12abef33")
    assert cm.to_hex(r, g, b, a, include_alpha=True) == "#12abef33"


def test_mix_midpoint():
    red = (255, 0, 0, 255)
    blue = (0, 0, 255, 255)
    mid = cm.mix(red, blue, 0.5)
    # Should approximate purple
    assert mid[0] in {127, 128}
    assert mid[2] in {127, 128}
    assert mid[1] == 0


def test_mix_gamma_correct_changes_result():
    red = (255, 0, 0, 255)
    blue = (0, 0, 255, 255)
    linear_mid = cm.mix(red, blue, 0.5, gamma_correct=True)
    simple_mid = cm.mix(red, blue, 0.5, gamma_correct=False)
    assert linear_mid != simple_mid  # gamma adjustment difference


def test_alpha_composite_basic():
    fg = (255, 0, 0, 128)
    bg = (0, 0, 255, 255)
    out = cm.alpha_composite(fg, bg)
    # Result should have full alpha (since bg is opaque)
    assert out[3] == 255
    # Red > 0 and Blue > 0 due to mixing
    assert out[0] > 0 and out[2] > 0


def test_invalid_parse():
    with pytest.raises(ValueError):
        cm.parse_hex("red")
    with pytest.raises(ValueError):
        cm.parse_hex("#1")


def test_mix_invalid_t():
    with pytest.raises(ValueError):
        cm.mix((0, 0, 0, 255), (255, 255, 255, 255), -0.1)
    with pytest.raises(ValueError):
        cm.mix((0, 0, 0, 255), (255, 255, 255, 255), 1.1)


def test_to_hex_clamping():
    assert cm.to_hex(300, -20, 10) == "#ff000a"
    assert cm.to_hex(10, 20, 30, 500, include_alpha=True) == "#0a141eff"
