"""DockManager - registry for dockable panels (Milestone 2.1).

Lightweight, test-friendly abstraction that avoids hard-coding widget creation
into the main window. Each dock is registered with an id and a factory that
returns a QWidget (the inner content). The manager creates a QDockWidget when
asked, assigning allowed areas and remembering instance references.

No persistent layout serialization yet (future milestone). Designed for
headless test by avoiding immediate QWidget creation until explicitly
instantiated under a running QApplication.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Union
from PyQt6.QtWidgets import QDockWidget, QWidget
from PyQt6.QtCore import Qt


__all__ = ["DockDefinition", "DockManager"]


@dataclass(frozen=True)
class DockDefinition:
    dock_id: str
    title: str
    factory: Callable[[], QWidget]
    allowed_areas: Union[int, "Qt.DockWidgetArea"]  # raw flags or int


class DockManager:
    def __init__(self) -> None:
        self._defs: Dict[str, DockDefinition] = {}
        self._instances: Dict[str, QDockWidget] = {}

    # Registration -----------------------------------------------------
    def register(
        self,
        dock_id: str,
        title: str,
        factory: Callable[[], QWidget],
        *,
        allowed_areas: Optional[int] = None,
    ) -> None:
        if dock_id in self._defs:
            raise ValueError(f"Duplicate dock id: {dock_id}")
        if allowed_areas is None and hasattr(Qt, "DockWidgetArea"):
            # Compose flags; in PyQt6 these are Flag enums (bitwise-or returns a new Flag)
            flags = (
                Qt.DockWidgetArea.LeftDockWidgetArea
                | Qt.DockWidgetArea.RightDockWidgetArea
                | Qt.DockWidgetArea.TopDockWidgetArea
                | Qt.DockWidgetArea.BottomDockWidgetArea
            )
            allowed_areas = flags
        self._defs[dock_id] = DockDefinition(
            dock_id=dock_id,
            title=title,
            factory=factory,
            allowed_areas=allowed_areas or 0,
        )

    def list_ids(self) -> List[str]:
        return sorted(self._defs.keys())

    def is_registered(self, dock_id: str) -> bool:
        return dock_id in self._defs

    # Creation ---------------------------------------------------------
    def create(self, dock_id: str):  # -> QDockWidget (runtime optional)
        if dock_id in self._instances:
            return self._instances[dock_id]
        definition = self._defs.get(dock_id)
        if definition is None:
            raise KeyError(dock_id)
        widget = definition.factory()
        dock_widget = QDockWidget(definition.title)
        dock_widget.setObjectName(dock_id)
        dock_widget.setWidget(widget)
        # allowed areas
        if hasattr(dock_widget, "setAllowedAreas") and definition.allowed_areas:
            try:
                dock_widget.setAllowedAreas(definition.allowed_areas)  # type: ignore[arg-type]
            except TypeError:
                # If stored as int but needs enum, skip or attempt simple conversion
                pass
        self._instances[dock_id] = dock_widget
        return dock_widget

    def get(self, dock_id: str):  # -> Optional[QDockWidget]
        return self._instances.get(dock_id)

    def instances(self):  # -> List[QDockWidget]
        return list(self._instances.values())
