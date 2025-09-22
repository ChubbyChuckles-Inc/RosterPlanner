"""Density service (Milestone 5.10.7).

Bridges `DensityManager` (scales spacing tokens) with runtime application and
publishes a density-changed event so views can optionally relayout.

Responsibilities:
 - Provide current density mode ("comfortable" | "compact")
 - Switch mode and compute diff (changed spacing tokens)
 - Persist selection to AppConfig (via config_store) when changed
 - Publish an EventBus event for observers

The service is intentionally small; additional variants (e.g., "cozy") can be
added later once design tokens support intermediate scales.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping

from gui.design import DensityManager, load_tokens
from .service_locator import services
from .event_bus import EventBus, GUIEvent

try:  # Optional import for persistence (bootstrap registers app_config early)
    from gui.app.config_store import AppConfig, save_config
except Exception:  # pragma: no cover
    AppConfig = object  # type: ignore

    def save_config(cfg, base_dir=None):  # type: ignore
        return None


__all__ = ["DensityService", "get_density_service"]


@dataclass
class DensityService:
    manager: DensityManager

    @classmethod
    def create_default(cls) -> "DensityService":
        tokens = load_tokens()
        # Bootstrap may have already stored a density mode in AppConfig
        cfg = services.try_get("app_config")
        initial_mode = "comfortable"
        if cfg and getattr(cfg, "density_mode", None) in ("comfortable", "compact"):
            initial_mode = getattr(cfg, "density_mode")  # type: ignore
        mgr = DensityManager(tokens, mode=initial_mode)  # type: ignore[arg-type]
        return cls(manager=mgr)

    def mode(self) -> str:
        return self.manager.mode

    def spacing(self) -> Mapping[str, int]:
        return self.manager.active_spacing()

    def set_mode(self, mode: str):  # type: ignore[override]
        if mode not in ("comfortable", "compact"):
            raise ValueError(f"Unsupported density mode: {mode}")
        diff = self.manager.set_mode(mode)  # type: ignore[arg-type]
        if not diff.no_changes:
            # Persist change to AppConfig if available
            cfg = services.try_get("app_config")
            if cfg and getattr(cfg, "density_mode", None) != mode:
                try:
                    cfg.density_mode = mode  # type: ignore[attr-defined]
                    save_config(cfg)
                except Exception:  # pragma: no cover - persistence best-effort
                    pass
            # Publish event
            try:
                bus = services.get_typed("event_bus", EventBus)
                bus.publish("density_changed", {"mode": mode, "changed": list(diff.changed.keys())})
            except Exception:  # pragma: no cover
                pass
        return diff


def get_density_service() -> DensityService:
    return services.get_typed("density_service", DensityService)
