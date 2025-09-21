"""Cursor affordance registry.

Provides a semantic mapping from interaction intent (e.g. resize, drag,
link, wait) to concrete cursor identifiers. Centralizing this allows the
GUI layer to remain consistent and makes it easier to later adapt to OS
preferences or theming (e.g., high contrast or large cursor modes).

Design Goals:
- Declarative dataclass capturing metadata (id, description, fallback Qt name)
- Registry with add/get/list/clear operations
- Prevent duplicate ids for safety
- Provide a set of canonical defaults aligned with milestone 0.37
- Pure Python (no PyQt6 import) to keep logic testable without Qt runtime

If PyQt6 integration is needed later, another module can translate the
``qt_cursor_name`` attribute into ``Qt.CursorShape`` values at runtime.

Public API:
- register_cursor_affordance(CursorAffordance)
- get_cursor_affordance(id: str) -> CursorAffordance | None
- list_cursor_affordances() -> list[CursorAffordance]
- clear_cursor_affordances()
- ensure_default_cursor_affordances() -> int (number added)

Edge Cases:
- Duplicate registration raises ValueError
- Unknown retrieval returns None

Testing Strategy:
- Ensure defaults load correctly and are idempotent
- Duplicate prevention
- Clear + re-register path
- Metadata integrity (non-empty id, description)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

__all__ = [
    "CursorAffordance",
    "register_cursor_affordance",
    "get_cursor_affordance",
    "list_cursor_affordances",
    "clear_cursor_affordances",
    "ensure_default_cursor_affordances",
]


@dataclass(frozen=True)
class CursorAffordance:
    """Semantic cursor affordance descriptor.

    Attributes
    ----------
    id: str
        Stable identifier (e.g. "resize-ew", "drag", "wait").
    description: str
        Human-readable explanation for documentation / dev tools.
    qt_cursor_name: str
        Name corresponding (loosely) to Qt cursor shape enum member (without
        relying on PyQt6 import here). Example: "SizeHorCursor".
    """

    id: str
    description: str
    qt_cursor_name: str

    def __post_init__(self):  # type: ignore[override]
        if not self.id or not self.id.strip():
            raise ValueError("cursor affordance id must be non-empty")
        if not self.description.strip():
            raise ValueError("cursor affordance description must be non-empty")
        if not self.qt_cursor_name.strip():
            raise ValueError("cursor affordance qt_cursor_name must be non-empty")


_registry: Dict[str, CursorAffordance] = {}


def register_cursor_affordance(aff: CursorAffordance) -> None:
    """Register a new cursor affordance.

    Raises ValueError if id already exists.
    """
    if aff.id in _registry:
        raise ValueError(f"cursor affordance with id '{aff.id}' already registered")
    _registry[aff.id] = aff


def get_cursor_affordance(aff_id: str) -> Optional[CursorAffordance]:
    return _registry.get(aff_id)


def list_cursor_affordances() -> List[CursorAffordance]:
    return list(_registry.values())


def clear_cursor_affordances() -> None:
    _registry.clear()


_DEFAULTS = [
    CursorAffordance("default", "Standard pointer", "ArrowCursor"),
    CursorAffordance("link", "Indicates clickable navigation", "PointingHandCursor"),
    CursorAffordance("text", "Text selection / edit region", "IBeamCursor"),
    CursorAffordance("move", "Generic move/drag handle", "SizeAllCursor"),
    CursorAffordance("drag", "Dragging content or item", "ClosedHandCursor"),
    CursorAffordance("dragging", "While actively dragging", "OpenHandCursor"),
    CursorAffordance("resize-ew", "Horizontal resize handle", "SizeHorCursor"),
    CursorAffordance("resize-ns", "Vertical resize handle", "SizeVerCursor"),
    CursorAffordance("resize-nesw", "Diagonal resize (NE/SW)", "SizeBDiagCursor"),
    CursorAffordance("resize-nwse", "Diagonal resize (NW/SE)", "SizeFDiagCursor"),
    CursorAffordance("wait", "Operation in progress (blocking)", "BusyCursor"),
    CursorAffordance("progress", "Background operation in progress", "WaitCursor"),
    CursorAffordance("precision", "Precision crosshair selection", "CrossCursor"),
    CursorAffordance("forbidden", "Action not allowed here", "ForbiddenCursor"),
]


def ensure_default_cursor_affordances() -> int:
    """Register default affordances if not already present.

    Returns number of defaults added on this call.
    """
    added = 0
    for aff in _DEFAULTS:
        if aff.id not in _registry:
            _registry[aff.id] = aff
            added += 1
    return added
