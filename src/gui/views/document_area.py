"""DocumentArea - tabbed central workspace (Milestone 2.1.1).

Lightweight wrapper around QTabWidget that:
 - Prevents duplicate logical documents (by doc_id)
 - Provides open_or_focus(doc_id, title, factory)
 - Emits a simple Python callback hook (on_changed) when current tab changes

Future enhancements (later milestones):
 - Persistence of open tab order
 - Close handling + dirty state prompts
 - Context menu actions (close others, pin, etc.)
"""

from __future__ import annotations
from typing import Callable, Dict, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from PyQt6.QtWidgets import QTabWidget, QWidget
else:  # runtime fallback without Qt
    QTabWidget = object  # type: ignore
    QWidget = object  # type: ignore

__all__ = ["DocumentArea"]


class DocumentArea(QTabWidget):  # type: ignore[misc]
    # (Could add a Qt signal later if needed; for now simple override)
    def __init__(self):
        super().__init__()  # type: ignore
        self._doc_index: Dict[str, int] = {}

    # Public API -----------------------------------------------------
    def open_or_focus(self, doc_id: str, title: str, factory: Callable[[], Any]) -> Any:
        if doc_id in self._doc_index:
            idx = self._doc_index[doc_id]
            self.setCurrentIndex(idx)  # type: ignore[attr-defined]
            return self.widget(idx)  # type: ignore[attr-defined]
        widget = factory()
        idx = self.addTab(widget, title)  # type: ignore[attr-defined]
        self._doc_index[doc_id] = idx
        self.setCurrentIndex(idx)  # type: ignore[attr-defined]
        return widget

    def has_document(self, doc_id: str) -> bool:
        return doc_id in self._doc_index

    def document_widget(self, doc_id: str) -> Optional[Any]:
        if doc_id not in self._doc_index:
            return None
        return self.widget(self._doc_index[doc_id])  # type: ignore[attr-defined]
