import pytest
from gui.design import load_tokens


def test_heading_font_sizes_progression():
    tokens = load_tokens()
    h1 = tokens.heading_font_size("h1")
    h2 = tokens.heading_font_size("h2")
    h3 = tokens.heading_font_size("h3")
    h4 = tokens.heading_font_size("h4")
    h5 = tokens.heading_font_size("h5")
    h6 = tokens.heading_font_size("h6")
    # Assert strictly decreasing or equal (allow ties only if intentional; here we expect strictly desc)
    assert h1 > h2 > h3 > h4 > h5 > h6


def test_heading_scale_factor_application():
    tokens = load_tokens()
    base_h3 = tokens.heading_font_size("h3")
    scaled_h3 = tokens.heading_font_size("h3", scale_factor=1.25)
    assert scaled_h3 == int(round(base_h3 * 1.25))
    # scale factor below 1 still returns at least 1
    tiny = tokens.heading_font_size("h6", scale_factor=0.01)
    assert tiny == 1


def test_font_family_present():
    tokens = load_tokens()
    fam = tokens.font_family()
    assert "Segoe" in fam or "Inter" in fam  # simple presence check
