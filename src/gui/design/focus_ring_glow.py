"""Focus ring glow variant (Milestone 5.10.31).

Builds an optional outer glow style QSS snippet layered on top of the base
focus ring, respecting reduced motion (skip glow) and high contrast mode
(
  - In high contrast: remove soft blur / opacity effects to maintain crisp edge
  - In reduced motion: also skip glow to avoid visual distraction
). The actual detection of high contrast is delegated to a simple injectable
predicate for testability (future integration may query OS / theme variant).

Public API:
 - build_focus_glow_qss(color: str, *, radius_px: int = 4, spread_px: int = 2,
                        opacity: float = 0.5, reduced_motion: bool | None = None,
                        high_contrast: bool | None = None) -> str

Returns an empty string when glow is disabled by environment flags.

Design Choices:
 - QSS uses box-shadow like emulation via outline + qproperty if later extended;
   for now we return a comment + outline style that can be concatenated into
   a widget's stylesheet fragment.
 - Kept pure (no PyQt imports) to simplify testing.
 - Future: integrate with dynamic theme accent extraction to compute color.
"""

from __future__ import annotations

from typing import Optional

from .reduced_motion import is_reduced_motion

__all__ = ["build_focus_glow_qss"]


def build_focus_glow_qss(
    color: str,
    *,
    radius_px: int = 4,
    spread_px: int = 2,
    opacity: float = 0.5,
    reduced_motion: Optional[bool] = None,
    high_contrast: Optional[bool] = None,
) -> str:
    """Return QSS snippet for glow focus ring or empty string if disabled.

    Parameters
    ----------
    color: str
        Base accent color (hex #RRGGBB expected). Opacity applied separately.
    radius_px: int
        Outline radius.
    spread_px: int
        Simulated blur/spread thickness (adds to visual radius in shadow emulation).
    opacity: float
        0..1 alpha for glow.
    reduced_motion: bool | None
        Override reduced motion detection (for tests). None -> query global.
    high_contrast: bool | None
        Explicit high contrast override; when True disables glow.
    """
    if not color.startswith("#") or len(color) not in {7, 9}:
        raise ValueError("color must be #RRGGBB or #RRGGBBAA")
    if radius_px < 0 or spread_px < 0:
        raise ValueError("radius_px and spread_px must be >= 0")
    if not (0.0 <= opacity <= 1.0):
        raise ValueError("opacity must be between 0 and 1")

    rm = is_reduced_motion() if reduced_motion is None else reduced_motion
    hc = bool(high_contrast) if high_contrast is not None else False

    if rm or hc:
        return ""  # disabled

    # Convert opacity to alpha hex (round) if no alpha component already
    base = color
    if len(base) == 7:
        alpha = int(round(opacity * 255))
        base = f"{base}{alpha:02X}"

    # Provide a pseudo style that can be appended; QSS doesn't support box-shadow,
    # but we can emulate with an outline (inset) plus transparent border layering.
    # Downstream integration may wrap this in a :focus selector.
    return (
        f"/* focus glow */\n"
        f"outline: {spread_px}px solid {base};\n"
        f"outline-offset: 0px;\n"
        f"border-radius: {radius_px + spread_px}px;\n"
    )
