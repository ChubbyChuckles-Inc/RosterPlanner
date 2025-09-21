"""Tests for print stylesheet generator (Milestone 0.28)."""

from gui.design.print_stylesheet import build_print_stylesheet, PrintStylesheetMeta


def test_build_print_stylesheet_basic():
    css, meta = build_print_stylesheet()
    assert isinstance(css, str)
    assert isinstance(meta, PrintStylesheetMeta)
    # Required baseline rules present
    assert "QWidget" in css
    assert meta.high_contrast is True


def test_build_print_stylesheet_with_tokens_and_no_high_contrast():
    tokens = {"color-primary": "#123456", "spacing-sm": "4px"}
    css, meta = build_print_stylesheet(tokens=tokens, high_contrast=False)
    # Deterministic ordering => color-primary first alphabetically
    first_index = css.index("color-primary")
    second_index = css.index("spacing-sm")
    assert first_index < second_index
    assert meta.included_tokens == 2
    assert meta.high_contrast is False
    # High contrast overrides absent
    assert "QPushButton { background: #FFFFFF; border: 2px solid #000000;" not in css
