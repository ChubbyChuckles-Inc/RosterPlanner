"""Contrast utilities for validating design token accessibility.

Implements WCAG 2.1 contrast ratio calculations.

Public API:
- contrast_ratio(fg: str, bg: str) -> float
- relative_luminance(color: str) -> float
- validate_contrast(tokens: DesignTokens, pairs: list[tuple[str,str,str]], threshold: float=4.5) -> list[str]

The `pairs` parameter uses tuples of (foreground_path, background_path, name) where each
path is dot-separated referencing color tokens (e.g. "text.primary", "background.base").
"""

from __future__ import annotations

from typing import Iterable, Tuple, List

from .loader import DesignTokens

_HEX_ERR = "Color must be a #RRGGBB hex string: {value}"


def _parse_hex(color: str) -> tuple[int, int, int]:
    if not isinstance(color, str) or not color.startswith("#") or len(color) != 7:
        raise ValueError(_HEX_ERR.format(value=color))
    r = int(color[1:3], 16)
    g = int(color[3:5], 16)
    b = int(color[5:7], 16)
    return r, g, b


def _linear_channel(c: float) -> float:
    c = c / 255.0
    if c <= 0.03928:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(color: str) -> float:
    r, g, b = _parse_hex(color)
    r_l = _linear_channel(r)
    g_l = _linear_channel(g)
    b_l = _linear_channel(b)
    # Rec. 709 coefficients used by WCAG
    return 0.2126 * r_l + 0.7152 * g_l + 0.0722 * b_l


def contrast_ratio(fg: str, bg: str) -> float:
    l1 = relative_luminance(fg)
    l2 = relative_luminance(bg)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _resolve_color(tokens: DesignTokens, path: str) -> str:
    parts = path.split(".")
    return tokens.color(*parts)


def validate_contrast(
    tokens: DesignTokens, pairs: Iterable[Tuple[str, str, str]], threshold: float = 4.5
) -> List[str]:
    """Validate a collection of foreground/background token pairs.

    Parameters
    ----------
    tokens : DesignTokens
        Loaded tokens instance.
    pairs : Iterable[Tuple[str,str,str]]
        Each tuple is (foreground_token_path, background_token_path, label)
    threshold : float
        Minimum acceptable contrast ratio.

    Returns
    -------
    list[str]
        A list of failure messages (empty if all pass).
    """
    failures: List[str] = []
    for fg_path, bg_path, label in pairs:
        try:
            fg = _resolve_color(tokens, fg_path)
            bg = _resolve_color(tokens, bg_path)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"[resolve-error] {label}: {exc}")
            continue
        ratio = contrast_ratio(fg, bg)
        if ratio < threshold:
            failures.append(
                f"[contrast-fail] {label}: ratio={ratio:.2f} < {threshold} (fg={fg} bg={bg})"
            )
    return failures


__all__ = [
    "contrast_ratio",
    "relative_luminance",
    "validate_contrast",
]
