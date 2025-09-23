"""Contextual radius adaptation (Milestone 5.10.29).

Maps semantic component roles (surface, panel, card, button, chip, pill) to
numeric corner radii sourced from design tokens. Centralizing this mapping
ensures consistent curvature scale across the UI and provides a single place
to tune future design shifts (e.g., brand theme variants lowering corner
roundness, or accessibility preference for higher contrast geometry).

Design Principles:
 - Semantic First: Components ask for a *role* not a raw radius value.
 - Monotonic Scale: xs < sm < md < lg < xl < pill.
 - Extensible: Additional roles can be appended without breaking API.
 - Testable: Pure functions, token loader injectable.

Public API:
 - RadiusRole (Literal type alias)
 - get_radius(role: RadiusRole, tokens: Optional[DesignTokens] = None) -> int
 - list_radius_roles() -> list[str]
 - RADIUS_ROLE_MAP constant (role -> token key)

Roles & Rationale:
 - surface: Large background surfaces (window-level) -> md (soft but subtle)
 - panel: Dock or grouped panel container -> lg (slightly more pronounced)
 - card: Elevated content containers -> lg
 - button: Interactive standard buttons -> sm (crisp tap targets)
 - chip: Small filter tags / tokens -> pill if width dynamic, else full pill styling
 - pill: Dedicated pill elements (segmented control, status badges) -> pill (999)
 - input: Form fields -> md (consistent with panel/card blend)
 - focus-ring-inner: Styling reference for internal focus outline radius -> button radius (sm)

Fallback Strategy:
If a token key is missing the loader falls back to a hardcoded conservative
value (4) except for 'pill' which always resolves to 999 to preserve shape.

Tests cover:
 - All roles resolve to int
 - Monotonic increasing ordering for base scale tokens
 - Pill extremely large
 - Missing token scenario (simulated) returns fallback
"""

from __future__ import annotations

from typing import Dict, List, Optional, Literal

from .loader import load_tokens, DesignTokens

__all__ = [
    "RadiusRole",
    "RADIUS_ROLE_MAP",
    "get_radius",
    "list_radius_roles",
]

RadiusRole = Literal[
    "surface",
    "panel",
    "card",
    "button",
    "input",
    "chip",
    "pill",
    "focus-ring-inner",
]


# Map radius roles to token keys present in tokens.json under radius.*
RADIUS_ROLE_MAP: Dict[RadiusRole, str] = {
    "surface": "md",
    "panel": "lg",
    "card": "lg",
    "button": "sm",
    "input": "md",
    "chip": "xl",  # visually distinct but not fully pill by default
    "pill": "pill",  # always extremely rounded
    "focus-ring-inner": "sm",
}


def _get_radius_token(tokens: DesignTokens, key: str) -> int:
    raw_radius = tokens.raw.get("radius", {})
    value = raw_radius.get(key)
    if value is None:
        # Fallback: conservative default; pill special-case
        return 999 if key == "pill" else 4
    if not isinstance(value, (int, float)):
        raise TypeError(f"Radius token '{key}' must be numeric, got {type(value)!r}")
    return int(value)


def get_radius(role: RadiusRole, tokens: Optional[DesignTokens] = None) -> int:
    """Return numeric radius for a semantic role.

    Parameters
    ----------
    role: RadiusRole
        Semantic role key.
    tokens: DesignTokens | None
        Optional token object; if omitted loads global tokens via loader.
    """
    if role not in RADIUS_ROLE_MAP:
        raise KeyError(f"Unknown radius role: {role}")
    t = tokens or load_tokens()
    token_key = RADIUS_ROLE_MAP[role]
    return _get_radius_token(t, token_key)


def list_radius_roles() -> List[str]:
    return list(RADIUS_ROLE_MAP.keys())
