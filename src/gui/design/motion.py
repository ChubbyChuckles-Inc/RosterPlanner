"""Motion utilities: easing curve parsing and duration lookup.

Provides a lightweight adapter around the design tokens motion section.
Does not require PyQt imports for testability; a helper stub is provided
for future integration with QPropertyAnimation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Tuple, Dict

from .loader import DesignTokens

__all__ = [
    "CubicBezier",
    "get_duration_ms",
    "get_easing_curve",
]

CubicBezier = Tuple[float, float, float, float]


@dataclass
class MotionSpec:
    durations: Mapping[str, int]
    easings: Mapping[str, str]

    def duration(self, name: str) -> int:
        if name not in self.durations:
            raise KeyError(f"Unknown motion duration token: {name}")
        return self.durations[name]

    def easing(self, name: str) -> CubicBezier:
        raw = self.easings.get(name)
        if raw is None:
            raise KeyError(f"Unknown easing token: {name}")
        return parse_cubic_bezier(raw)


def build_motion_spec(tokens: DesignTokens) -> MotionSpec:
    motion = tokens.raw.get("motion", {})
    durations = motion.get("duration", {})
    easings = motion.get("easing", {})
    return MotionSpec(durations=durations, easings=easings)


def parse_cubic_bezier(spec: str) -> CubicBezier:
    """Parse a CSS-like cubic-bezier string into numeric tuple.

    Expected format: 'cubic-bezier(x1, y1, x2, y2)'. Whitespace tolerated.
    Values are converted to float.
    """
    s = spec.strip().lower()
    if not s.startswith("cubic-bezier(") or not s.endswith(")"):
        raise ValueError(f"Invalid cubic-bezier format: {spec}")
    inner = s[len("cubic-bezier(") : -1]
    parts = [p.strip() for p in inner.split(",")]
    if len(parts) != 4:
        raise ValueError(f"cubic-bezier requires 4 components, got {len(parts)}: {spec}")
    try:
        x1, y1, x2, y2 = (float(p) for p in parts)
    except ValueError as e:  # pragma: no cover - unlikely
        raise ValueError(f"Non-numeric cubic-bezier value in {spec}") from e
    return x1, y1, x2, y2


# Convenience functions (stateless wrappers)


def get_duration_ms(tokens: DesignTokens, name: str) -> int:
    return build_motion_spec(tokens).duration(name)


def get_easing_curve(tokens: DesignTokens, name: str) -> CubicBezier:
    return build_motion_spec(tokens).easing(name)
