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
    "tab_traversal_widgets",
    "tab_traversal_names",
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


# Real Tab traversal (best-effort) ---------------------------------------------------


def tab_traversal_widgets(root_factory: Callable[[], QWidget], *, max_steps: int = 50) -> List[QWidget]:  # type: ignore[name-defined]
    """Attempt to perform real Tab traversal using QTest.

    Returns the ordered list of distinct focus widgets visited until the
    cycle repeats or `max_steps` reached.

    Skips quietly (returns empty list) if PyQt test utilities are missing
    or a QApplication cannot be created.
    """
    try:  # Runtime imports (avoid hard dependency when unused)
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtTest import QTest  # type: ignore
        from PyQt6.QtCore import Qt
    except Exception:  # pragma: no cover - environment w/out PyQt test stack
        return []

    app = QApplication.instance()
    if app is None:  # pragma: no cover - usually created elsewhere
        try:
            app = QApplication([])  # type: ignore[arg-type]
        except Exception:
            return []

    root = root_factory()
    try:
        root.show()
    except Exception:  # pragma: no cover - defensive
        return []
    app.processEvents()

    # Seed initial focus: pick first logical focusable widget if none focused
    if not app.focusWidget():
        logical = compute_logical_focus_order(lambda: root)
        if logical:
            logical[0].widget.setFocus()
            app.processEvents()

    visited: List[QWidget] = []  # type: ignore[name-defined]
    first: QWidget | None = None  # type: ignore[name-defined]

    for _ in range(max_steps):
        current = app.focusWidget()
        if current is None:
            break
        if not visited:
            first = current
        if current not in visited:
            visited.append(current)
        else:
            if current is first:
                break  # Completed a cycle
        # Advance focus
        try:
            QTest.keyClick(current, Qt.Key.Key_Tab)
        except Exception:  # pragma: no cover - defensive
            break
        app.processEvents()

    try:  # Cleanup
        root.close()
    except Exception:
        pass
    return visited


def tab_traversal_names(root_factory: Callable[[], QWidget], *, max_steps: int = 50) -> List[str]:  # type: ignore[name-defined]
    widgets = tab_traversal_widgets(root_factory, max_steps=max_steps)
    names: List[str] = []
    for w in widgets:
        try:
            name = w.objectName()  # type: ignore[attr-defined]
            if name:
                names.append(name)
            else:
                names.append(w.__class__.__name__)
        except Exception:  # pragma: no cover - defensive
            names.append("<unknown>")
    return names
