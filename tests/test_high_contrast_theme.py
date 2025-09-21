from __future__ import annotations

from gui.design import load_tokens
from gui.design.contrast import contrast_ratio, relative_luminance


def test_high_contrast_variant_presence():
    tokens = load_tokens()
    assert tokens.is_high_contrast_supported()
    default = tokens.theme_variant("default")
    high = tokens.theme_variant("high-contrast")
    # Ensure some key semantic domains differ (background.base vs high variant)
    assert default["background.base"] != high["background.base"]
    assert default["text.primary"] == high["text.primary"] or contrast_ratio(
        default["text.primary"], high["background.base"]
    ) >= contrast_ratio(default["text.primary"], default["background.base"])


def test_high_contrast_improves_contrast_for_secondary_text():
    tokens = load_tokens()
    default = tokens.theme_variant("default")
    high = tokens.theme_variant("high-contrast")
    d_ratio = contrast_ratio(default["text.secondary"], default["background.base"])
    h_ratio = contrast_ratio(high["text.secondary"], high["background.base"])
    # Allow equality but expect not worse by more than a tiny epsilon
    assert h_ratio + 0.01 >= d_ratio
