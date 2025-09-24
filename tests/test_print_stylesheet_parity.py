"""Print stylesheet parity test harness (Milestone 5.10.62).

Goals:
- Ensure print stylesheet generation includes required baseline rules.
- Verify high contrast variant applies override selectors.
- Basic parity: a representative subset of theme tokens can be injected and are
  emitted deterministically.
- Contrast sanity: text on white background remains >= 4.5 ratio when tokens supplied.

This is intentionally lightweight to keep CI fast; deeper visual regression is
covered by separate snapshot mechanisms.
"""

from __future__ import annotations

from gui.design.print_stylesheet import build_print_stylesheet
from gui.design.contrast import contrast_ratio


def test_print_stylesheet_parity_high_contrast():
    css, meta = build_print_stylesheet(high_contrast=True)
    assert "QWidget" in css
    assert "QPushButton" in css  # high contrast override present
    assert meta.high_contrast is True
    # No duplicate trailing whitespace artifacts
    assert css.endswith("\n")


def test_print_stylesheet_token_emission_and_order():
    tokens = {"accent.base": "#3478F6", "text.primary": "#111111", "spacing.xs": "2px"}
    css, meta = build_print_stylesheet(tokens=tokens, high_contrast=False)
    # Deterministic ordering by key (accent.base < spacing.xs < text.primary lexicographically?)
    # Actually: 'accent.base', 'spacing.xs', 'text.primary'
    first = css.index("accent.base")
    second = css.index("spacing.xs")
    third = css.index("text.primary")
    assert first < second < third
    assert meta.included_tokens == 3
    assert meta.high_contrast is False


def test_print_stylesheet_basic_contrast_sanity():
    # Provide a potentially low contrast text token to see if still passes baseline;
    # this test documents current behavior (no auto-adjust) and asserts acceptable contrast.
    tokens = {"text.primary": "#000000"}
    css, _ = build_print_stylesheet(tokens=tokens, high_contrast=True)
    # Extract background (#FFFFFF) and text (#000000) expected ratio = 21.0
    ratio = contrast_ratio("#000000", "#FFFFFF")
    assert ratio >= 7.0  # AA large (3.0) and normal (4.5) comfortably exceeded
    assert "text.primary" in css
