from __future__ import annotations

import pytest

from gui.services.theme_service import ThemeService
from gui.design.contrast import contrast_ratio


@pytest.fixture(scope="module")
def svc() -> ThemeService:
    return ThemeService.create_default()


def test_available_variants_contains_overlays(svc: ThemeService):
    variants = svc.available_variants()
    # Expect a representative subset of new overlays
    expected = {"midnight", "ocean", "slate-light"}
    assert expected.issubset(set(variants))


@pytest.mark.parametrize(
    "variant",
    [
        "default",
        "brand-neutral",
        "high-contrast",
        "midnight",
        "dim",
        "ocean",
        "forest",
        "mono-high",
        "slate-light",
        "solarized-light",
        "high-contrast-light",
    ],
)
def test_variant_contrast_and_required_keys(svc: ThemeService, variant: str):
    svc.set_variant(variant)
    colors = svc.colors()
    # Required keys exist (at least those listed in REQUIRED_COLOR_KEYS)
    required = [
        "background.primary",
        "background.secondary",
        "surface.card",
        "text.primary",
        "text.muted",
        "accent.base",
    ]
    for key in required:
        assert key in colors and colors[key], f"Missing {key} for variant {variant}"
    bg = colors.get("background.primary")
    txt = colors.get("text.primary")
    muted = colors.get("text.muted")
    if bg and txt:
        assert contrast_ratio(txt, bg) >= 4.5, f"Primary text contrast too low for {variant}"
    if bg and muted:
        assert contrast_ratio(muted, bg) >= 3.0, f"Muted text contrast too low for {variant}"
