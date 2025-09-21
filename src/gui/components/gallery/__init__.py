"""Component Gallery infrastructure (internal QA tool).

Purpose:
 - Register lightweight demo factories for components and surface them in a
     simple inspection window (when PyQt available).
 - Provide maturity badges (alpha/beta/stable) inline using design registry.

Design Constraints:
 - Pure-Python at import time (no Qt hard dependency) for testability.
 - Thread-safe registration via `RLock`.
 - Graceful degradation if maturity registry not present.

Stability: Alpha – internal tooling; API may evolve as gallery features grow.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional
from threading import RLock

__all__ = [
    "GalleryEntry",
    "register_demo",
    "list_demos",
    "get_demo",
    "clear_demos",
    "build_list_item_label",
]

DemoFactory = Callable[[], object]  # returns a QWidget (when PyQt available)

_lock = RLock()
_registry: Dict[str, "GalleryEntry"] = {}

# Optional import of component maturity registry (design system Milestone 0.49)
try:  # pragma: no cover - import side-effect only
    from gui.design.component_maturity import (  # type: ignore
        get_component_maturity,  # noqa: F401
    )
except Exception:  # pragma: no cover - graceful fallback if design layer not present
    get_component_maturity = None  # type: ignore


@dataclass
class GalleryEntry:
    name: str
    category: str
    factory: DemoFactory
    description: str = ""
    hidden: bool = False

    def create(self) -> object:
        return self.factory()


# ---------------------------- Maturity Integration Helpers -----------------------
def _maturity_badge(component_name: str) -> str:
    """Return a maturity badge string (e.g., " [ALPHA]") for a component name.

    If the component maturity registry is unavailable or the component is not
    registered, returns an empty string. Stable components still receive a
    badge for explicit transparency.
    """
    if get_component_maturity is None:  # type: ignore
        return ""
    try:
        entry = get_component_maturity(component_name)  # type: ignore
    except Exception:  # noqa: BLE001
        return ""
    return f" [{entry.status.upper()}]"


def build_list_item_label(demo: GalleryEntry) -> str:
    """Build the list label for a gallery demo, including maturity badge.

    Pure function for easy testing (no Qt dependency)."""
    return f"{demo.category} / {demo.name}{_maturity_badge(demo.name)}"


def register_demo(
    name: str,
    category: str,
    factory: DemoFactory,
    *,
    description: str = "",
    hidden: bool = False,
    override: bool = False,
) -> None:
    if not name:
        raise ValueError("Demo name required")
    with _lock:
        if name in _registry and not override:
            raise KeyError(f"Demo already registered: {name}")
        _registry[name] = GalleryEntry(
            name=name,
            category=category,
            factory=factory,
            description=description,
            hidden=hidden,
        )


def list_demos(include_hidden: bool = False) -> List[GalleryEntry]:
    with _lock:
        values = list(_registry.values())
    if include_hidden:
        return values
    return [e for e in values if not e.hidden]


def get_demo(name: str) -> GalleryEntry:
    with _lock:
        if name not in _registry:
            raise KeyError(name)
        return _registry[name]


def clear_demos() -> None:
    with _lock:
        _registry.clear()


# Optional GUI window scaffold (lazy) -------------------------------------------------


def build_gallery_window(parent=None):  # pragma: no cover - minimal placeholder
    try:
        from PyQt6.QtWidgets import (
            QWidget,
            QVBoxLayout,
            QListWidget,
            QListWidgetItem,
            QLabel,
            QSplitter,
        )
    except Exception:  # PyQt6 not available
        raise RuntimeError("PyQt6 not available for gallery window")

    root = QWidget(parent)
    root.setWindowTitle("RosterPlanner Component Gallery")
    layout = QVBoxLayout(root)
    try:
        splitter = QSplitter()
        list_widget = QListWidget()
        detail = QLabel("Select a component demo")
        detail.setWordWrap(True)
        splitter.addWidget(list_widget)
        splitter.addWidget(detail)
        layout.addWidget(splitter)

        demos = sorted(list_demos(), key=lambda d: (d.category, d.name))
        for demo in demos:
            item = QListWidgetItem(build_list_item_label(demo))
            item.setData(256, demo.name)  # Qt.UserRole = 256
            list_widget.addItem(item)

        def on_current_changed():
            item = list_widget.currentItem()
            if not item:
                return
            name = item.data(256)
            entry = get_demo(name)
            # Replace detail widget content lazily
            try:
                widget = entry.create()
                detail.setText(f"Loaded demo: {entry.name}\n{entry.description}")
                # In future we might embed 'widget' into a preview container
            except Exception as exc:  # noqa: BLE001
                detail.setText(f"Failed to create demo: {exc}")

        list_widget.currentItemChanged.connect(lambda *_: on_current_changed())  # type: ignore
    except Exception:  # noqa: BLE001 - defensive
        pass
    return root
