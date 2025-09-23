"""Theme awareness utilities (Milestone 5.10.13).

Provides a light-weight mixin that widgets can inherit to receive
notifications when the active theme changes WITHOUT requiring each
view to manually subscribe to the EventBus.

Propagation Strategy
--------------------
The MainWindow (or any root container choosing to) performs a recursive
walk over its child widget tree when a GUIEvent.THEME_CHANGED event is
published. Any object that is an instance of ThemeAwareMixin will have
`on_theme_changed(theme_service, changed_keys)` invoked.

This keeps coupling low (widgets do not directly import or depend on
EventBus) and keeps the propagation mechanism centralized.

Guidelines for Implementers
---------------------------
- Keep `on_theme_changed` idempotent and inexpensive; it may be called
  multiple times rapidly (e.g., during stress test scripts).
- Cache expensive derived objects (e.g., QPixmaps) behind the current
  theme hash if necessary.
- Avoid triggering layout thrashing; prefer direct property updates or
  stylesheet adjustments localized to the widget.
"""

from __future__ import annotations
from typing import List, Protocol, runtime_checkable

if False:  # pragma: no cover - type checking only
    from gui.services.theme_service import ThemeService

__all__ = ["ThemeAwareMixin", "ThemeAwareProtocol"]


@runtime_checkable
class ThemeAwareProtocol(Protocol):  # pragma: no cover - structural protocol
    def on_theme_changed(self, theme: "ThemeService", changed_keys: List[str]) -> None: ...


class ThemeAwareMixin:
    """Mixin providing a hook for theme updates.

    Subclasses should override `on_theme_changed`.
    This base class only serves as an anchor for isinstance checks.
    """

    def on_theme_changed(
        self, theme: "ThemeService", changed_keys: List[str]
    ) -> None:  # pragma: no cover - override in subclass
        pass
