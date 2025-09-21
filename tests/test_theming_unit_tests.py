from pathlib import Path

from src.gui.design import load_tokens, DesignTokens

# Required semantic groups we expect for baseline theming confidence.
REQUIRED_COLOR_GROUPS = ["background", "surface", "text", "accent", "border"]


def test_tokens_load_and_required_groups_present():
    tokens = load_tokens()
    raw = tokens.raw
    assert "color" in raw
    color = raw["color"]
    for group in REQUIRED_COLOR_GROUPS:
        assert group in color, f"Missing color group '{group}'"
        assert isinstance(color[group], dict)
        # expect at least one string entry
        assert any(isinstance(v, str) for v in color[group].values()), f"Group {group} empty"


def test_theme_variant_non_null_values():
    tokens = load_tokens()
    variant = tokens.theme_variant("default")
    assert variant, "Variant mapping should not be empty"
    for k, v in variant.items():
        assert isinstance(v, str) and v.strip(), f"Variant value for {k} is blank"


def test_high_contrast_variant_fallbacks():
    tokens = load_tokens()
    default = tokens.theme_variant("default")
    high = tokens.theme_variant("high-contrast")
    # High contrast may reuse defaults for groups not overridden, so ensure keys superset equality.
    assert set(default.keys()).issubset(set(high.keys()))


def test_heading_font_sizes_positive():
    tokens = load_tokens()
    for heading in tokens.heading_levels():
        size = tokens.heading_font_size(heading, scale_factor=1.0)
        assert size > 0


def test_generate_qss_contains_color_comments():
    tokens = load_tokens()
    qss = tokens.generate_qss()
    # Expect at least one comment referencing color.
    assert "color." in qss
