"""Color mixing utilities (Milestone 0.39).

Provides small, dependency-free helpers for:
- Parsing hex colors (#rgb, #rgba, #rrggbb, #rrggbbaa) into RGBA tuples
- Converting RGBA tuples back to normalized hex (#rrggbb / #rrggbbaa)
- Linear interpolation (mix) between two colors
- Alpha compositing (A over B) in sRGB
- Optional gamma-aware mixing (approx sRGB to linear and back)

These utilities support later design tooling (layered surfaces, overlay
translucency, token derivation). They avoid external libraries for minimal
footprint and deterministic behavior.

Accepted component range: 0-255 for channels, 0-1 float for factor.

Public API:
    parse_hex(color: str) -> (r,g,b,a)
    to_hex(r,g,b,a=255, include_alpha=False) -> str
    mix(c1, c2, t: float, gamma_correct=False) -> (r,g,b,a)
    alpha_composite(fg, bg) -> (r,g,b,a)
    blend_over(fg, bg) -> (r,g,b,a)  (alias for alpha_composite)

Notes:
    - parse_hex always returns tuple of ints (0-255) including alpha (default 255)
    - mix linearly interpolates alpha separately; if gamma_correct=True, RGB
      are transformed using simple sRGB <-> linear approximations.
"""

from __future__ import annotations

from typing import Tuple

__all__ = [
    "parse_hex",
    "to_hex",
    "mix",
    "alpha_composite",
    "blend_over",
]

RGBA = Tuple[int, int, int, int]


def parse_hex(color: str) -> RGBA:
    """Parse a hex color string into (r,g,b,a) tuple.

    Supports #rgb, #rgba, #rrggbb, #rrggbbaa (case-insensitive).
    Raises ValueError for invalid format.
    """
    if not isinstance(color, str):
        raise ValueError("color must be a string")
    c = color.strip()
    if not c.startswith("#"):
        raise ValueError("hex color must start with '#'")
    c = c[1:]
    if len(c) == 3:  # rgb
        r, g, b = (int(ch * 2, 16) for ch in c)
        return r, g, b, 255
    if len(c) == 4:  # rgba
        r, g, b, a = (int(ch * 2, 16) for ch in c)
        return r, g, b, a
    if len(c) == 6:  # rrggbb
        r = int(c[0:2], 16)
        g = int(c[2:4], 16)
        b = int(c[4:6], 16)
        return r, g, b, 255
    if len(c) == 8:  # rrggbbaa
        r = int(c[0:2], 16)
        g = int(c[2:4], 16)
        b = int(c[4:6], 16)
        a = int(c[6:8], 16)
        return r, g, b, a
    raise ValueError("invalid hex color length")


def _clamp_byte(v: int) -> int:
    return 0 if v < 0 else 255 if v > 255 else v


def to_hex(r: int, g: int, b: int, a: int = 255, *, include_alpha: bool = False) -> str:
    """Convert RGBA components to hex string.

    If include_alpha is False, alpha is ignored in output even if not 255.
    Values outside 0-255 are clamped.
    """
    r = _clamp_byte(r)
    g = _clamp_byte(g)
    b = _clamp_byte(b)
    a = _clamp_byte(a)
    if include_alpha:
        return f"#{r:02x}{g:02x}{b:02x}{a:02x}"
    return f"#{r:02x}{g:02x}{b:02x}"


def _srgb_to_linear(c: float) -> float:
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(c: float) -> float:
    if c <= 0.0031308:
        return 12.92 * c
    return 1.055 * (c ** (1 / 2.4)) - 0.055


def mix(c1: RGBA, c2: RGBA, t: float, *, gamma_correct: bool = False) -> RGBA:
    """Linearly mix two RGBA colors by factor t in [0,1].

    When gamma_correct=True, performs mixing in linear space for RGB.
    Alpha mixed linearly always.
    """
    if not 0 <= t <= 1:
        raise ValueError("t must be between 0 and 1")
    r1, g1, b1, a1 = c1
    r2, g2, b2, a2 = c2
    if gamma_correct:
        # convert to 0-1
        lr1, lg1, lb1 = (
            _srgb_to_linear(r1 / 255.0),
            _srgb_to_linear(g1 / 255.0),
            _srgb_to_linear(b1 / 255.0),
        )
        lr2, lg2, lb2 = (
            _srgb_to_linear(r2 / 255.0),
            _srgb_to_linear(g2 / 255.0),
            _srgb_to_linear(b2 / 255.0),
        )
        lr = lr1 + (lr2 - lr1) * t
        lg = lg1 + (lg2 - lg1) * t
        lb = lb1 + (lb2 - lb1) * t
        r = int(round(_linear_to_srgb(lr) * 255))
        g = int(round(_linear_to_srgb(lg) * 255))
        b = int(round(_linear_to_srgb(lb) * 255))
    else:
        r = int(round(r1 + (r2 - r1) * t))
        g = int(round(g1 + (g2 - g1) * t))
        b = int(round(b1 + (b2 - b1) * t))
    a = int(round(a1 + (a2 - a1) * t))
    return _clamp_byte(r), _clamp_byte(g), _clamp_byte(b), _clamp_byte(a)


def alpha_composite(fg: RGBA, bg: RGBA) -> RGBA:
    """Composite foreground over background (both RGBA 0-255)."""
    fr, fg_r, fb, fa = fg
    br, bg_r, bb, ba = bg
    af = fa / 255.0
    ab = ba / 255.0
    out_a = af + ab * (1 - af)
    if out_a == 0:
        return 0, 0, 0, 0
    # Pre-multiplied logic
    r = int(round((fr * af + br * ab * (1 - af)) / out_a))
    g = int(round((fg_r * af + bg_r * ab * (1 - af)) / out_a))
    b = int(round((fb * af + bb * ab * (1 - af)) / out_a))
    return _clamp_byte(r), _clamp_byte(g), _clamp_byte(b), int(round(out_a * 255))


blend_over = alpha_composite
