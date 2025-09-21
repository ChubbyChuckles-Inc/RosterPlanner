"""Accessibility focus order utilities.

Provides helpers to introspect a QWidget hierarchy (built by a factory) and
produce an ordered list of widgets that would normally participate in Tab
focus traversal according to Qt's focus chain rules.

We avoid simulating actual key events here (QTest dependency) to keep this
layer minimal and headless-safe. Instead, we approximate focus order using:
- QWidget.focusPolicy()
- QWidget.isEnabled()
- QWidget.isVisible()
- Child widget stacking / creation order (depth-first traversal)

This is sufficient for unit-level verification that a composite component
registers its child controls in a logical, user-friendly order.

Future Enhancements:
- Optional integration with QTest to simulate real Tab traversal
- Heuristics for skipping decorative containers automatically
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, List, Any, Protocol

__all__ = [
    "FocusEntry",
    "compute_logical_focus_order",
    "focus_order_names",
]

try:  # Import guarded for environments without PyQt during non-GUI tests
    from PyQt6.QtWidgets import QWidget  # type: ignore
    from PyQt6.QtCore import Qt  # type: ignore
except Exception:  # pragma: no cover - allows pure logic tests to import module

    class QWidget:  # type: ignore
        """Fallback QWidget stub for typing when PyQt6 not present."""

        def focusPolicy(self) -> int:  # noqa: D401 - simple stub
            return 0

        def isEnabled(self) -> bool:
            return False

        def isVisible(self) -> bool:
            return False

        def findChildren(self, _type):  # noqa: D401 - stub
            return []

    class Qt:  # type: ignore
        class FocusPolicy:  # Minimal sentinel
            NoFocus = 0


@dataclass
class FocusEntry:
    widget: QWidget
    path: str  # dot/path-like hierarchy identifier

    @property
    def object_name(self) -> str:
        try:
            return getattr(self.widget, "objectName", lambda: "")() or ""
        except Exception:  # noqa: BLE001
            return ""


def _iter_children(parent: QWidget) -> Iterable[Any]:  # pragma: no cover - trivial
    try:
        return parent.findChildren(QWidget)
    except Exception:
        return []


def _is_focusable(w: QWidget) -> bool:
    try:
        policy = w.focusPolicy()
        enabled = w.isEnabled()
        visible = w.isVisible()
        if not enabled or not visible:
            return False
        # Accept anything except NoFocus
        if hasattr(policy, "__int__"):
            return int(policy) != 0
        return policy != 0
    except Exception:  # noqa: BLE001 - defensive
        return False


def compute_logical_focus_order(root_factory: Callable[[], QWidget]) -> List[FocusEntry]:
    """Build widget via factory and derive focus order list.

    The traversal is depth-first based on child enumeration returned by
    QWidget.findChildren, filtered to focusable widgets.
    """
    root = root_factory()
    order: List[FocusEntry] = []

    def visit(w: QWidget, path: str):
        if _is_focusable(w):
            order.append(FocusEntry(widget=w, path=path))
        for idx, child in enumerate(_iter_children(w)):
            visit(child, f"{path}.{idx}")

    visit(root, "root")
    return order


def focus_order_names(entries: List[FocusEntry]) -> List[str]:
    names: List[str] = []
    for e in entries:
        n = e.object_name
        if n:
            names.append(n)
        else:
            names.append(e.widget.__class__.__name__)
    return names
