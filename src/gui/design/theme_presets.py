"""Additional theme variant overlay presets.

Each preset is a flat mapping of semantic color role -> hex value that will be
overlaid on top of the base token-derived theme (the `default` variant in
`ThemeManager`). Only a small subset of roles is required; any omitted keys
fall back to the underlying token map.

Guiding principles:
 - Maintain WCAG AA contrast for `text.primary` (>=4.5) and `text.muted` (>=3.0)
 - Provide both dark and light families
 - Keep accent colors vivid but not neon; hover/active derive slightly lighter/darker
 - Avoid dependency on Qt (pure data)

Future: Could load these dynamically from user config or plugin directories.
"""

from __future__ import annotations

from typing import Dict, Mapping

OverlayMap = Dict[str, str]

_PRESETS: dict[str, OverlayMap] = {
    # Dark family -----------------------------------------------------
    "midnight": {
        "background.primary": "#0E1116",
        "background.secondary": "#161B22",
        "surface.card": "#1C232B",
        "text.primary": "#F2F5F8",
        "text.muted": "#A8B3BF",
        "accent.base": "#3D82F6",
        "accent.hover": "#5694FA",
        "accent.active": "#2C6AD4",
        "border.medium": "#2A323C",
    },
    "dim": {
        "background.primary": "#1E1F23",
        "background.secondary": "#26272B",
        "surface.card": "#2D2F34",
        "text.primary": "#ECEEEF",
        "text.muted": "#B1B5BA",
        "accent.base": "#4C8DFF",
        "accent.hover": "#5E99FF",
        "accent.active": "#3A74D6",
        "border.medium": "#3A3D44",
    },
    "ocean": {
        "background.primary": "#0F1F2B",
        "background.secondary": "#152935",
        "surface.card": "#1B3140",
        "text.primary": "#F1F7FA",
        "text.muted": "#AAC2CD",
        "accent.base": "#1FA2B8",
        "accent.hover": "#27B6CE",
        "accent.active": "#158CA0",
        "border.medium": "#254452",
    },
    "forest": {
        "background.primary": "#101E14",
        "background.secondary": "#182A1E",
        "surface.card": "#203527",
        "text.primary": "#F0F7F2",
        "text.muted": "#B2C5BA",
        "accent.base": "#3FA55B",
        "accent.hover": "#52B56C",
        "accent.active": "#318349",
        "border.medium": "#294632",
    },
    "mono-high": {  # Grayscale emphasis
        "background.primary": "#121212",
        "background.secondary": "#1E1E1E",
        "surface.card": "#262626",
        "text.primary": "#FFFFFF",
        "text.muted": "#B5B5B5",
        "accent.base": "#FFFFFF",
        "accent.hover": "#E6E6E6",
        "accent.active": "#CCCCCC",
        "border.medium": "#3A3A3A",
    },
    # Light family ----------------------------------------------------
    "slate-light": {
        "background.primary": "#F5F7FA",
        "background.secondary": "#EDF1F5",
        "surface.card": "#FFFFFF",
        "text.primary": "#1F2428",
        "text.muted": "#4F5B66",
        "accent.base": "#2563EB",
        "accent.hover": "#3975F1",
        "accent.active": "#1E55C9",
        "border.medium": "#D0D6DD",
    },
    "solarized-light": {
        "background.primary": "#FDF6E3",
        "background.secondary": "#F4EAD0",
        "surface.card": "#FFFFFF",
        "text.primary": "#073642",
        "text.muted": "#586E75",
        "accent.base": "#268BD2",
        "accent.hover": "#3799DE",
        "accent.active": "#1E74B4",
        "border.medium": "#D3C7AF",
    },
    "high-contrast-light": {
        "background.primary": "#FFFFFF",
        "background.secondary": "#F2F2F2",
        "surface.card": "#FFFFFF",
        "text.primary": "#000000",
        "text.muted": "#2E2E2E",
        "accent.base": "#005FCC",
        "accent.hover": "#1A74D6",
        "accent.active": "#004899",
        "border.medium": "#4D4D4D",
    },
}


def get_overlay(variant: str) -> OverlayMap | None:
    return _PRESETS.get(variant)


def available_variant_overlays() -> list[str]:
    return list(_PRESETS.keys())


__all__ = ["get_overlay", "available_variant_overlays"]
