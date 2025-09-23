"""Adaptive contrast utilities (Milestone 5.10.24).

Provides helpers to automatically assign readable foreground colors for accent
surfaces based on WCAG contrast thresholds. This complements the existing
`ThemeService._normalize_contrast` logic which handles global text roles.

Primary export:
    ensure_accent_on_color(mapping) -> mutates mapping in-place adding
    `accent.on` if missing or insufficient contrast relative to `accent.base`.

Rules:
 - If `accent.base` absent, no-op.
 - If `accent.on` already present and contrast >= 4.5: keep.
 - Else choose white vs black whichever yields higher contrast (must be >= 4.5
   to be considered valid). If both < 4.5 choose the higher anyway as a
   best-effort fallback.

This keeps implementation lean and testable; future expansion might consider
dynamic scaling, outline addition, or advanced perceptual adjustments.
"""

from __future__ import annotations

from typing import Mapping
from .contrast import contrast_ratio

__all__ = ["ensure_accent_on_color"]


def ensure_accent_on_color(mapping: Mapping[str, str]) -> None:
    try:
        accent = mapping.get("accent.base")  # type: ignore
    except Exception:  # pragma: no cover - defensive
        return
    if not accent:
        return
    current = mapping.get("accent.on")  # type: ignore
    if current and contrast_ratio(current, accent) >= 4.5:
        return  # Already acceptable
    white_c = contrast_ratio("#FFFFFF", accent)
    black_c = contrast_ratio("#000000", accent)
    chosen = "#FFFFFF" if white_c >= black_c else "#000000"
    # Mapping may be a plain dict; attempt assignment and ignore failures for Mapping subclasses.
    try:  # type: ignore[attr-defined]
        mapping["accent.on"] = chosen  # type: ignore
    except Exception:  # pragma: no cover
        pass
