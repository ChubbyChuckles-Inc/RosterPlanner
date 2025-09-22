"""Semantic typography role helpers (Milestone 5.10.3).

Provides a stable indirection between UI code and raw token keys so future
scale adjustments or adaptive user preferences can be centralized.

Roles map to either heading levels (h1..h6) or base scale tokens (sm, md, lg).
Each accessor returns a `QFont` instance configured with family, pixel size,
and optional weight adjustments. We keep weight handling conservative until
design finalizes a weight scale.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict
from PyQt6.QtGui import QFont
from .loader import load_tokens


class TypographyRole(Enum):
    TITLE = "title"  # Primary view titles
    SUBTITLE = "subtitle"  # Secondary headings within a view
    BODY = "body"  # Standard body text
    CAPTION = "caption"  # Ancillary metadata / subtle labels


_ROLE_TO_HEADING: Dict[TypographyRole, str] = {
    TypographyRole.TITLE: "h3",  # Reasonable default size for dock/view titles
    TypographyRole.SUBTITLE: "h5",
    TypographyRole.BODY: "h6",  # Map body to smallest heading for consistency
    TypographyRole.CAPTION: "xs",  # Direct scale token (not a heading alias)
}


def font_for_role(role: TypographyRole, scale_factor: float = 1.0) -> QFont:
    tokens = load_tokens()
    fam = tokens.font_family()
    mapping = _ROLE_TO_HEADING.get(role)
    if mapping is None:
        raise KeyError(role)
    if mapping.startswith("h"):
        px = tokens.heading_font_size(mapping, scale_factor=scale_factor)
    else:
        px = int(round(tokens.font_size(mapping) * scale_factor))
    f = QFont(fam)
    f.setPixelSize(px)
    if role in (TypographyRole.TITLE, TypographyRole.SUBTITLE):
        f.setWeight(QFont.Weight.Bold)
    return f


__all__ = ["TypographyRole", "font_for_role"]
