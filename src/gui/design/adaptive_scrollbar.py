"""Adaptive scrollbar styling (Milestone 0.47).

Generates theme-aware QSS for scrollbars with semantic token references.
We avoid hardcoding colors by referencing entries in a provided theme map
(`dict[str, str]`) which would originate from `ThemeManager.active_map`.

Goals
-----
 - Cross-platform consistency (Qt style differs per OS; QSS overlay provides uniform look)
 - Accessible contrast: rely on existing surface/background/text/accent tokens
 - Customizable thickness & radius parameters (defaults chosen for balance)
 - Minimal selector set: vertical & horizontal scrollbars, handle (thumb), add/sub line (arrows), corner

Design Decisions
----------------
 - Use semantic keys: surface.scroll.track, surface.scroll.trackHover, surface.scroll.handle,
   surface.scroll.handleHover, surface.scroll.handleActive, border.focus, accent.primary
 - Provide graceful fallback if a key is missing: fallback order -> close semantic group -> generic surface/text token -> #888 placeholder.
 - Provide a single factory `build_scrollbar_styles` returning QSS string.
 - Keep purely functional & side-effect free for testability.

Future Enhancements (Not in scope now)
-------------------------------------
 - Auto contrast adjustment (lighten/darken based on background luminance)
 - Reduced motion adaptation for hover transitions
 - High-contrast variant overrides (could call again with variant map)
"""

from __future__ import annotations

from typing import Mapping, Sequence

__all__ = ["build_scrollbar_styles"]


_FALLBACK_ORDER: Mapping[str, Sequence[str]] = {
    "surface.scroll.track": ("surface.primary", "background.base", "#2b2b2b"),
    "surface.scroll.trackHover": (
        "surface.scroll.track",
        "surface.primary",
        "background.alt",
        "#333333",
    ),
    "surface.scroll.handle": ("surface.raised", "surface.primary", "#555555"),
    "surface.scroll.handleHover": (
        "surface.scroll.handle",
        "surface.raised",
        "surface.primary",
        "#666666",
    ),
    "surface.scroll.handleActive": (
        "surface.scroll.handleHover",
        "surface.scroll.handle",
        "accent.primary",
        "#777777",
    ),
    "border.focus": ("accent.primary", "#0080ff"),
}


def _resolve(theme_map: Mapping[str, str], key: str) -> str:
    if key in theme_map:
        return theme_map[key]
    order = _FALLBACK_ORDER.get(key)
    if not order:
        return theme_map.get("surface.primary", theme_map.get("background.base", "#888888"))
    for candidate in order:
        if candidate in theme_map and theme_map[candidate]:
            return theme_map[candidate]
        if candidate.startswith("#"):
            return candidate
    return "#888888"


def build_scrollbar_styles(
    theme_map: Mapping[str, str], *, width: int = 10, radius: int = 4
) -> str:
    """Build QSS for adaptive scrollbars.

    Parameters
    ----------
    theme_map: Mapping[str, str]
        Flat mapping of theme token names to hex colors (e.g., from ThemeManager.active_map)
    width: int
        Thickness of scrollbar track in px.
    radius: int
        Corner radius for handle (thumb) and track.
    """

    w = max(4, min(width, 30))  # clamp to sane bounds
    r = max(0, min(radius, 16))
    track = _resolve(theme_map, "surface.scroll.track")
    track_hover = _resolve(theme_map, "surface.scroll.trackHover")
    handle = _resolve(theme_map, "surface.scroll.handle")
    handle_hover = _resolve(theme_map, "surface.scroll.handleHover")
    handle_active = _resolve(theme_map, "surface.scroll.handleActive")
    focus_border = _resolve(theme_map, "border.focus")

    # Note: Qt distinguishes vertical/horizontal via :vertical / :horizontal selectors
    qss = f"""
/* Adaptive Scrollbar (generated) */
QScrollBar:vertical {{
    background: {track};
    width: {w}px;
    margin: 0px;
    border: none;
    border-radius: {r}px;
}}
QScrollBar:vertical:hover {{
    background: {track_hover};
}}
QScrollBar::handle:vertical {{
    background: {handle};
    min-height: {w * 2}px;
    border-radius: {r}px;
}}
QScrollBar::handle:vertical:hover {{
    background: {handle_hover};
}}
QScrollBar::handle:vertical:pressed {{
    background: {handle_active};
    border: 1px solid {focus_border};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px; /* remove arrow buttons */
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}

QScrollBar:horizontal {{
    background: {track};
    height: {w}px;
    margin: 0px;
    border: none;
    border-radius: {r}px;
}}
QScrollBar:horizontal:hover {{
    background: {track_hover};
}}
QScrollBar::handle:horizontal {{
    background: {handle};
    min-width: {w * 2}px;
    border-radius: {r}px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {handle_hover};
}}
QScrollBar::handle:horizontal:pressed {{
    background: {handle_active};
    border: 1px solid {focus_border};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: transparent;
}}
QScrollBar:vertical:disabled, QScrollBar:horizontal:disabled {{
    opacity: 0.4;
}}
""".strip()
    return qss
