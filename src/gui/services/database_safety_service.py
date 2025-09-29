"""Database safety mode service (Milestone 7.11.5).

Provides a persisted toggle controlling whether the Database Panel operates in
read-only mode or exposes administrative actions. The toggle state is stored in
:class:`gui.app.config_store.AppConfig` so it survives application restarts.

The service also emits a lightweight event via the global event bus when the
mode changes, allowing interested views to react without tight coupling.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from gui.app.config_store import AppConfig, save_config
from gui.services.service_locator import services

try:  # Optional dependency; the event bus may not be registered in some tests
    from gui.services.event_bus import EventBus
except Exception:  # pragma: no cover
    EventBus = object  # type: ignore

__all__ = ["DatabaseSafetyService", "get_database_safety_service"]


@dataclass
class DatabaseSafetyService:
    """Centralizes the Database Panel safety mode toggle."""

    app_config: Optional[AppConfig] = None
    base_dir: Optional[str | Path] = None

    def __post_init__(self) -> None:
        stored = False
        if self.app_config is not None and hasattr(self.app_config, "database_admin_mode"):
            stored = bool(getattr(self.app_config, "database_admin_mode"))
        self._admin_enabled = stored

    # ------------------------------------------------------------------
    def admin_enabled(self) -> bool:
        """Return whether administrative mode is currently enabled."""

        return self._admin_enabled

    def set_admin_enabled(self, enabled: bool) -> bool:
        """Update the administrative mode flag.

        Returns ``True`` if the value changed, ``False`` otherwise. When the
        value changes it is persisted (best effort) and a notification event is
        published via the event bus if available.
        """

        if self._admin_enabled == enabled:
            return False
        self._admin_enabled = enabled
        if self.app_config is not None:
            try:
                self.app_config.database_admin_mode = enabled  # type: ignore[attr-defined]
                save_config(self.app_config, self.base_dir)
            except Exception:  # pragma: no cover - persistence is best-effort
                pass
        self._publish_change(enabled)
        return True

    def toggle(self) -> bool:
        """Invert the administrative mode toggle and return ``True`` if it changed."""

        return self.set_admin_enabled(not self._admin_enabled)

    # ------------------------------------------------------------------
    def _publish_change(self, enabled: bool) -> None:
        bus = services.try_get("event_bus")
        if bus and isinstance(bus, EventBus):  # type: ignore[arg-type]
            try:
                bus.publish(
                    "database_admin_mode_changed",
                    {"admin_enabled": enabled},
                )
            except Exception:  # pragma: no cover - notification is best-effort
                pass


def get_database_safety_service() -> DatabaseSafetyService:
    """Retrieve the shared :class:`DatabaseSafetyService` instance."""

    return services.get_typed("database_safety_service", DatabaseSafetyService)
