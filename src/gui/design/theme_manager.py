"""Runtime theme management (hot-reload capable).

Provides a minimal `ThemeManager` responsible for:
 - Holding current theme variant (default | high-contrast)
 - Managing dynamic accent base & derived accent palette
 - Producing a flattened active color map (semantic -> hex)
 - Emitting diffs when updated (returns diff structure; future hook for EventBus)

The manager avoids direct Qt dependencies so it is testable headless.
Later we can integrate with an EventBus for UI-wide refresh notifications.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Literal, Mapping, Optional

from .loader import DesignTokens
from .dynamic_accent import derive_accent_palette

Variant = Literal["default", "high-contrast"]

__all__ = ["ThemeManager", "ThemeDiff"]


@dataclass
class ThemeDiff:
    """Represents changes between two theme states.

    Attributes
    ----------
    changed : dict[str, tuple[str|None, str|None]]
        Mapping of semantic key -> (old_value, new_value)
    no_changes : bool
        True if diff is empty.
    """

    changed: Dict[str, tuple[Optional[str], Optional[str]]]

    @property
    def no_changes(self) -> bool:  # noqa: D401 - trivial
        return not self.changed


@dataclass
class ThemeManager:
    tokens: DesignTokens
    variant: Variant = "default"
    accent_base: str = "#3D8BFD"
    _active_map: Dict[str, str] = field(default_factory=dict)
    _accent_cache: Dict[str, Dict[str, str]] = field(default_factory=dict)

    def __post_init__(self) -> None:  # Initialize active map
        self._rebuild_active_map()

    # Public API -----------------------------------------------------------
    def active_map(self) -> Mapping[str, str]:
        return self._active_map

    def set_variant(self, variant: Variant) -> ThemeDiff:
        if variant == self.variant:
            return ThemeDiff({})
        old = self._active_map.copy()
        self.variant = variant
        self._rebuild_active_map()
        return self._diff(old, self._active_map)

    def set_accent_base(self, base_hex: str) -> ThemeDiff:
        if base_hex.upper() == self.accent_base.upper():
            return ThemeDiff({})
        old = self._active_map.copy()
        self.accent_base = base_hex.upper()
        self._rebuild_active_map()
        return self._diff(old, self._active_map)

    # Internal -------------------------------------------------------------
    def _rebuild_active_map(self) -> None:
        base = dict(self.tokens.theme_variant(self.variant))
        # Merge accent palette (dynamic)
        palette = self._accent_cache.get(self.accent_base)
        if palette is None:
            palette = derive_accent_palette(self.accent_base)
            self._accent_cache[self.accent_base] = palette
        for k, v in palette.items():
            base[f"accent.{k}"] = v
        self._active_map = base

    @staticmethod
    def _diff(old: Mapping[str, str], new: Mapping[str, str]) -> ThemeDiff:
        changed: Dict[str, tuple[Optional[str], Optional[str]]] = {}
        keys = set(old.keys()) | set(new.keys())
        for k in keys:
            ov = old.get(k)
            nv = new.get(k)
            if ov != nv:
                changed[k] = (ov, nv)
        return ThemeDiff(changed)
