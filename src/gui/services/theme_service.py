"""Theme service (Milestone 1.6 initial implementation).

Bridges the headless `ThemeManager` (design tokens + accent derivation) with the
runtime application via the `EventBus`. Provides:

 - Light/Dark (default/high-contrast already handled by ThemeManager variants)
 - Accent color mutation
 - Emission of GUIEvent.THEME_CHANGED with a diff summary

The service keeps a cached active map for cheap access. Future expansion can
compute and apply QSS strings; for now it exposes the semantic color mapping
for consumers (e.g., style builders) and publishes theme change events.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from gui.design import ThemeManager, ThemeDiff, load_tokens
from .event_bus import EventBus, GUIEvent
from .service_locator import services

__all__ = ["ThemeService", "get_theme_service"]


@dataclass
class ThemeService:
    manager: ThemeManager
    _cached_map: dict[str, str]

    @classmethod
    def create_default(cls) -> "ThemeService":
        tokens = load_tokens()  # relies on design tokens module already supplying defaults
        mgr = ThemeManager(tokens)
        return cls(manager=mgr, _cached_map=dict(mgr.active_map()))

    # Accessors ---------------------------------------------------------
    def colors(self) -> Mapping[str, str]:
        return self._cached_map

    # Mutations ---------------------------------------------------------
    def set_variant(self, variant: str) -> ThemeDiff:
        diff = self.manager.set_variant(variant)  # type: ignore[arg-type]
        if not diff.no_changes:
            self._cached_map = dict(self.manager.active_map())
            self._publish_theme_changed(diff)
        return diff

    def set_accent(self, base_hex: str) -> ThemeDiff:
        diff = self.manager.set_accent_base(base_hex)
        if not diff.no_changes:
            self._cached_map = dict(self.manager.active_map())
            self._publish_theme_changed(diff)
        return diff

    # Internal ----------------------------------------------------------
    def _publish_theme_changed(self, diff: ThemeDiff) -> None:
        try:
            bus = services.get_typed("event_bus", EventBus)
        except Exception:  # pragma: no cover - if bus not yet registered
            return
        # Summarize changed keys (limit length to keep traces small)
        changed_keys = list(diff.changed.keys())
        summary = {"changed": changed_keys[:15], "count": len(changed_keys)}
        bus.publish(GUIEvent.THEME_CHANGED, summary)


def get_theme_service() -> ThemeService:
    return services.get_typed("theme_service", ThemeService)
