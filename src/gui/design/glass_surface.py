"""Glass surface variant helper (Milestone 5.10.22).

Provides a small utility to conditionally generate QSS snippets that emulate a
"glass" / translucent surface effect. Native real-time background blur is not
reliably available across all Qt builds/platforms without enabling
platform‑specific composition flags (and can incur a performance cost). This
module therefore exposes:

 - capability() -> GlassCapability describing whether the enhanced effect
   should be attempted based on platform, reduced motion preference, and an
   optional performance budget toggle.
 - build_glass_qss(role_bg, role_border, intensity) returning a QSS fragment
   with layered translucency + fallback solid background.

Strategy:
If capability is disabled we return a plain opaque surface style so consumers
can uniformly apply the snippet without branching logic at call sites.

Tests stub the platform + reduce motion flags to exercise both branches.
"""

from __future__ import annotations

from dataclasses import dataclass
import platform
from typing import Optional

__all__ = [
    "GlassCapability",
    "get_glass_capability",
    "build_glass_qss",
]


@dataclass(frozen=True)
class GlassCapability:
    supported: bool
    reason: str | None = None
    reduced_mode: bool = False  # e.g. OS reduced motion or accessibility constraint

    def effective(self) -> bool:
        """Return True if glass effect should be used.

        We treat reduced mode as a hard opt-out even if supported to respect
        accessibility preferences (aligns with ADR-0002 progressive enhancement
        constraints).
        """

        return self.supported and not self.reduced_mode


def _detect_reduced_motion() -> bool:
    # Placeholder: integrate with existing motion reduction service once
    # implemented. For now, environment variable check allows test forcing.
    import os

    return os.getenv("RP_REDUCED_MOTION", "0") in {"1", "true", "TRUE"}


def get_glass_capability(override_platform: Optional[str] = None) -> GlassCapability:
    sys_plat = (override_platform or platform.system()).lower()
    # Basic heuristic: enable only on Windows 10+/11 and macOS (where composition
    # with translucency is typically GPU accelerated). Linux support varies by window manager.
    if sys_plat.startswith("win"):
        supported = True
        reason = None
    elif sys_plat.startswith("darwin") or sys_plat.startswith("mac"):
        supported = True
        reason = None
    else:
        supported = False
        reason = "platform-not-whitelisted"
    reduced = _detect_reduced_motion()
    if reduced:
        reason = reason or "reduced-motion"
    return GlassCapability(supported=supported, reason=reason, reduced_mode=reduced)


def build_glass_qss(
    widget_selector: str,
    background_color: str,
    border_color: str,
    *,
    intensity: int = 25,
    capability: Optional[GlassCapability] = None,
) -> str:
    """Return a QSS snippet for a translucent glass-like surface.

    Parameters
    ----------
    widget_selector: str
        QSS selector (e.g. "QWidget#PlannerPanel").
    background_color: str
        Base opaque background fallback (token derived) e.g. #1E1E24.
    border_color: str
        Border color to maintain contrast boundaries.
    intensity: int
        Percentage alpha for the primary translucent layer (10..90 typical).
    capability: GlassCapability | None
        Pre-computed capability (optional for test override). If not provided
        will be detected on demand.
    """

    if capability is None:
        capability = get_glass_capability()
    # Clamp intensity
    if intensity < 5:
        intensity = 5
    if intensity > 95:
        intensity = 95
    alpha_hex = f"{int(255 * (intensity / 100)):02X}"
    # Layered approach: base transparent layer + subtle inner highlight. Real
    # backdrop blur would require platform window attributes (future).
    if capability.effective():
        return (
            f"{widget_selector} {{\n"
            f"  background: rgba({int(background_color[1:3],16)},{int(background_color[3:5],16)},{int(background_color[5:7],16)},{intensity/100:.2f});\n"
            f"  border:1px solid {border_color};\n"
            f"  border-radius:8px;\n"
            f"  /* simulated glass via translucent fill (no blur) */\n"
            f"}}\n"
            f"{widget_selector}::before {{ /* highlight overlay */\n"
            f"  content:'';\n"
            f"  position:absolute;\n"
            f"  top:0; left:0; right:0; height:40%;\n"
            f"  background: rgba(255,255,255,0.06);\n"
            f"  border-top-left-radius:8px; border-top-right-radius:8px;\n"
            f"}}"
        )
    # Fallback: solid surface maintaining identical border + radius
    return (
        f"{widget_selector} {{\n"
        f"  background: {background_color};\n"
        f"  border:1px solid {border_color};\n"
        f"  border-radius:8px;\n"
        f"  /* glass disabled: {capability.reason} */\n"
        f"}}"
    )
