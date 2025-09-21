from __future__ import annotations

from gui.design.dynamic_accent import derive_accent_palette
from gui.design.contrast import contrast_ratio


def test_accent_palette_keys_and_determinism():
    base = "#3D8BFD"
    p1 = derive_accent_palette(base)
    p2 = derive_accent_palette(base)
    assert p1 == p2  # Deterministic
    required = {
        "primary",
        "primaryHover",
        "primaryActive",
        "subtleBg",
        "subtleBorder",
        "emphasisBg",
        "outline",
    }
    assert required.issubset(p1.keys())


def test_accent_palette_contrast_improvement_paths():
    base = "#3D8BFD"
    palette = derive_accent_palette(base)
    # Hover should be lighter than active (approx by luminance)
    from gui.design.contrast import relative_luminance

    assert relative_luminance(palette["primaryHover"]) >= relative_luminance(palette["primaryActive"]) - 0.01


def test_subtle_border_darker_than_subtle_bg():
    base = "#3D8BFD"
    palette = derive_accent_palette(base)
    from gui.design.contrast import relative_luminance

    assert relative_luminance(palette["subtleBorder"]) < relative_luminance(palette["subtleBg"]) + 0.05
