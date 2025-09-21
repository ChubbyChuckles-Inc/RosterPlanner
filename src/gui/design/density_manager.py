"""Layout density management utilities.

Provides a lightweight manager to derive spacing values for different density
modes ("comfortable" vs "compact"). The manager avoids mutating the base
design tokens and instead presents a derived spacing map.

Future extensions: user-defined custom scales, per-component overrides.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Literal, Mapping

from .loader import DesignTokens

DensityMode = Literal["comfortable", "compact"]

__all__ = ["DensityManager", "DensityDiff", "DensityMode"]

_DEFAULT_SCALES: dict[DensityMode, float] = {
    "comfortable": 1.0,
    "compact": 0.8,
}


@dataclass
class DensityDiff:
    changed: Dict[str, tuple[int | None, int | None]]

    @property
    def no_changes(self) -> bool:  # noqa: D401 - trivial
        return not self.changed


@dataclass
class DensityManager:
    tokens: DesignTokens
    mode: DensityMode = "comfortable"
    scales: dict[DensityMode, float] = field(default_factory=lambda: dict(_DEFAULT_SCALES))
    _active: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._rebuild()

    def active_spacing(self) -> Mapping[str, int]:
        return self._active

    def set_mode(self, mode: DensityMode) -> DensityDiff:
        if mode == self.mode:
            return DensityDiff({})
        old = self._active.copy()
        self.mode = mode
        self._rebuild()
        return self._diff(old, self._active)

    # Utility for components wanting ad-hoc scaling of a literal value
    def scale_value(self, raw: int) -> int:
        if raw == 0:
            return 0
        factor = self.scales[self.mode]
        scaled = int(round(raw * factor))
        if scaled <= 0 and raw > 0:
            return 1
        return scaled

    def _rebuild(self) -> None:
        spacing_group = self.tokens.raw.get("spacing", {})
        derived: Dict[str, int] = {}
        for key, val in spacing_group.items():
            if isinstance(val, int):
                derived[key] = self.scale_value(val)
        self._active = derived

    @staticmethod
    def _diff(old: Mapping[str, int], new: Mapping[str, int]) -> DensityDiff:
        changed: Dict[str, tuple[int | None, int | None]] = {}
        keys = set(old.keys()) | set(new.keys())
        for k in keys:
            ov = old.get(k)
            nv = new.get(k)
            if ov != nv:
                changed[k] = (ov, nv)
        return DensityDiff(changed)
