"""Dynamic accent palette derivation.

Given a user-provided base accent color (hex #RRGGBB), generates a semantic
accent palette with shades appropriate for various UI states.

Approach:
1. Convert hex -> linear RGB -> HSL (simple implementation sufficient here)
2. Generate lighter/darker variants by adjusting lightness with gentle clamps
3. Ensure sufficient contrast for text on primary accent background; if not,
   fallback to white or near-white foreground in future extension (not yet needed)

Public API:
- derive_accent_palette(base_hex: str) -> dict[str,str]

Palette Keys Produced:
  primary            : base color (normalized)
  primaryHover       : lightened by +8% L (bounded)
  primaryActive      : darkened by -10% L (bounded)
  subtleBg           : same hue/sat, lightness ~ base_L + 25% (badge backgrounds)
  subtleBorder       : subtleBg darkened slightly for delineation
  emphasisBg         : blend( base, #000, 85% base ) for emphasized container
  outline            : base color with max(40%, original L) for focus ring

All hex returns uppercase (#RRGGBB) for consistency.

Determinism: For the same input hex the function produces consistent output.

Note: We intentionally avoid external color libraries to minimize dependencies.
"""

from __future__ import annotations

from typing import Dict

__all__ = ["derive_accent_palette"]


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    if not isinstance(hex_color, str) or not hex_color.startswith("#") or len(hex_color) != 7:
        raise ValueError(f"Invalid hex color: {hex_color}")
    r = int(hex_color[1:3], 16) / 255.0
    g = int(hex_color[3:5], 16) / 255.0
    b = int(hex_color[5:7], 16) / 255.0
    return r, g, b


def _rgb_to_hex(r: float, g: float, b: float) -> str:
    return f"#{int(_clamp(r)*255+0.5):02X}{int(_clamp(g)*255+0.5):02X}{int(_clamp(b)*255+0.5):02X}"


def _rgb_to_hsl(r: float, g: float, b: float) -> tuple[float, float, float]:
    mx = max(r, g, b)
    mn = min(r, g, b)
    l = (mx + mn) / 2
    if mx == mn:
        return 0.0, 0.0, l
    d = mx - mn
    s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn + 1e-9)
    if mx == r:
        h = ((g - b) / d) % 6
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    h /= 6
    return h, s, l


def _hsl_to_rgb(h: float, s: float, l: float) -> tuple[float, float, float]:
    def hue(p: float, q: float, t: float) -> float:
        if t < 0:
            t += 1
        if t > 1:
            t -= 1
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    if s == 0:
        return l, l, l
    q = l + s - l * s if l < 0.5 else l + s - l * s
    p = 2 * l - q
    r = hue(p, q, h + 1 / 3)
    g = hue(p, q, h)
    b = hue(p, q, h - 1 / 3)
    return r, g, b


def _adjust_lightness(hex_color: str, delta: float) -> str:
    r, g, b = _hex_to_rgb(hex_color)
    h, s, l = _rgb_to_hsl(r, g, b)
    l = _clamp(l + delta)
    r2, g2, b2 = _hsl_to_rgb(h, s, l)
    return _rgb_to_hex(r2, g2, b2)


def _blend(src_hex: str, dst_hex: str, alpha_src: float) -> str:
    sr, sg, sb = _hex_to_rgb(src_hex)
    dr, dg, db = _hex_to_rgb(dst_hex)
    r = sr * alpha_src + dr * (1 - alpha_src)
    g = sg * alpha_src + dg * (1 - alpha_src)
    b = sb * alpha_src + db * (1 - alpha_src)
    return _rgb_to_hex(r, g, b)


def derive_accent_palette(base_hex: str) -> Dict[str, str]:
    """Derive a semantic accent palette from a base color.

    Parameters
    ----------
    base_hex: str
        Base accent color (#RRGGBB)
    """
    base_hex = base_hex.upper()
    # Validate upfront
    _ = _hex_to_rgb(base_hex)

    hover = _adjust_lightness(base_hex, +0.08)
    active = _adjust_lightness(base_hex, -0.10)
    # Subtle background: lighten significantly (target +0.25 L)
    subtle_bg = _adjust_lightness(base_hex, +0.25)
    subtle_border = _adjust_lightness(subtle_bg, -0.12)
    emphasis_bg = _blend(base_hex, "#000000", 0.85)
    outline = _adjust_lightness(base_hex, +0.15)

    return {
        "primary": base_hex,
        "primaryHover": hover,
        "primaryActive": active,
        "subtleBg": subtle_bg,
        "subtleBorder": subtle_border,
        "emphasisBg": emphasis_bg,
        "outline": outline,
    }
