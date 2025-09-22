"""Dock registry (Milestone 2.2.1) providing an extensible factory catalog.

Separates *declaration* of available docks from the DockManager instance that
creates QDockWidgets. This enables:
 - Plugin-based dynamic registration (call register_dock before MainWindow init)
 - Central enumeration for layout persistence / migration

Design:
 - DockDefinition: (dock_id, title, factory)
 - Global _REGISTRY storing definitions in insertion order
 - Public API: register_dock, get_definition, iter_definitions, is_registered
 - Helper ensure_core_docks_registered to populate the initial baseline
 - Plugin extension point: add callables into PLUGIN_HOOKS list; MainWindow
   can invoke run_plugin_hooks() before enumerating docks.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Any, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from PyQt6.QtWidgets import QWidget
else:  # fallback type alias
    QWidget = Any  # type: ignore

__all__ = [
    "DockDefinition",
    "register_dock",
    "get_definition",
    "iter_definitions",
    "is_registered",
    "ensure_core_docks_registered",
    "PLUGIN_HOOKS",
    "run_plugin_hooks",
]


@dataclass(frozen=True)
class DockDefinition:
    dock_id: str
    title: str
    factory: Callable[[], QWidget]


_REGISTRY: Dict[str, DockDefinition] = {}
PLUGIN_HOOKS: List[Callable[[], None]] = []


def register_dock(dock_id: str, title: str, factory: Callable[[], QWidget]) -> None:
    if dock_id in _REGISTRY:
        raise ValueError(f"Dock already registered: {dock_id}")
    _REGISTRY[dock_id] = DockDefinition(dock_id, title, factory)


def get_definition(dock_id: str) -> DockDefinition:
    return _REGISTRY[dock_id]


def iter_definitions() -> Iterable[DockDefinition]:
    return _REGISTRY.values()


def is_registered(dock_id: str) -> bool:
    return dock_id in _REGISTRY


_CORE_IDS = [
    "navigation",
    "availability",
    "detail",
    "stats",
    "planner",
    "logs",
]


def ensure_core_docks_registered(factories: Dict[str, Callable[[], QWidget]]) -> None:
    """Register the baseline docks if not already present.

    The caller supplies a mapping of dock_id -> factory (so the registry does
    not import heavy GUI modules on its own). Missing entries raise.
    """
    for dock_id in _CORE_IDS:
        if dock_id not in factories:
            raise KeyError(f"Missing factory for required core dock id: {dock_id}")
    for dock_id in _CORE_IDS:
        if not is_registered(dock_id):
            register_dock(dock_id, dock_id.capitalize(), factories[dock_id])


def run_plugin_hooks() -> None:
    for hook in list(PLUGIN_HOOKS):  # copy to allow mutation
        hook()
