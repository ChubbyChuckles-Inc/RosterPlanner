"""Visual Selector Picker (Milestone 7.10.35)

Initial lightweight implementation (non-browser, static HTML) that allows a user
to click within a rendered minimal DOM tree representation and receive a
generated CSS-like selector path for the chosen element.

Constraints:
 - We do not embed a full web engine; instead we parse HTML with BeautifulSoup
   and build a simple QTreeWidget for structure.
 - Selector heuristic: tag + optional id + class list; descendant chain joined by ' > '.
 - Unique index disambiguation: if multiple sibling tags of same signature exist,
   add :nth-of-type(n) (1-based) for that step.

Future Enhancements (deferred):
 - Live highlighting within embedded WebView
 - XPath generation toggle
 - Copy-to-clipboard button
 - Hover preview of node text/attributes
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QPushButton,
    QLineEdit,
    QLabel,
)
from PyQt6.QtCore import Qt

try:
    from bs4 import BeautifulSoup  # type: ignore
except Exception:  # pragma: no cover
    BeautifulSoup = None  # type: ignore

__all__ = ["SelectorPickerDialog", "build_selector_for_item"]


def build_selector_for_item(item: QTreeWidgetItem) -> str:
    parts: List[str] = []
    cursor: Optional[QTreeWidgetItem] = item
    while cursor and cursor.parent() is not None:  # skip synthetic root
        sig = cursor.data(0, Qt.ItemDataRole.UserRole) or {}
        if isinstance(sig, dict):
            frag = sig.get("tag", "")
            el_id = sig.get("id")
            classes = sig.get("classes") or []
            if el_id:
                frag += f"#{el_id}"
            if classes:
                # Use only the first class for compactness and deterministic selector (tests expect single class)
                frag += f".{classes[0]}"
            # Sibling disambiguation
            parent = cursor.parent()
            if parent:
                same = [
                    parent.child(i)
                    for i in range(parent.childCount())
                    if (parent.child(i).data(0, Qt.ItemDataRole.UserRole) or {}).get("tag")
                    == sig.get("tag")
                ]
                if len(same) > 1:
                    # 1-based index
                    index = same.index(cursor) + 1
                    frag += f":nth-of-type({index})"
            parts.append(frag)
        cursor = cursor.parent()
    return " > ".join(reversed(parts))


try:  # pragma: no cover - guard for headless tests
    from gui.components.chrome_dialog import ChromeDialog
except Exception:  # pragma: no cover
    ChromeDialog = object  # type: ignore


class SelectorPickerDialog(ChromeDialog):  # type: ignore[misc]
    def __init__(self, html: str, parent=None):  # noqa: D401
        super().__init__(parent, title="Selector Picker")
        self.setObjectName("SelectorPickerDialog")
        lay = self.content_layout() if hasattr(self, "content_layout") else None
        if lay is None:  # fallback if ChromeDialog import failed
            from PyQt6.QtWidgets import QVBoxLayout, QWidget  # local import

            container = QWidget(self)
            lay = QVBoxLayout(container)
        self._tree = QTreeWidget()
        self._tree.setObjectName("selectorPickerTree")
        self._tree.setHeaderHidden(True)
        lay.addWidget(self._tree, 1)
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Selector:"))
        self.selector_edit = QLineEdit()
        self.selector_edit.setObjectName("selectorPickerOutput")
        out_row.addWidget(self.selector_edit, 1)
        self.btn_copy = QPushButton("Copy")
        self.btn_copy.setObjectName("selectorPickerCopy")
        out_row.addWidget(self.btn_copy)
        lay.addLayout(out_row)
        btns = QHBoxLayout()
        self.btn_ok = QPushButton("OK")
        self.btn_ok.setObjectName("selectorPickerOk")
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("selectorPickerCancel")
        btns.addStretch(1)
        btns.addWidget(self.btn_ok)
        btns.addWidget(self.btn_cancel)
        lay.addLayout(btns)
        try:
            self.btn_ok.clicked.connect(self.accept)  # type: ignore
            self.btn_cancel.clicked.connect(self.reject)  # type: ignore
            self._tree.itemClicked.connect(self._on_item_clicked)  # type: ignore
        except Exception:  # pragma: no cover
            pass
        try:
            self.resize(640, 520)
        except Exception:
            pass
        self._populate(html)

    # ------------------------------------------------------------------
    def _populate(self, html: str) -> None:
        self._tree.clear()
        if not BeautifulSoup:
            root = QTreeWidgetItem(["BeautifulSoup not installed"])
            self._tree.addTopLevelItem(root)
            return
        soup = BeautifulSoup(html, "html.parser")
        root = QTreeWidgetItem(["document"])
        root.setData(0, Qt.ItemDataRole.UserRole, {"tag": "document"})
        self._tree.addTopLevelItem(root)

        def add_children(bs_node, parent_item):  # noqa: ANN001
            for child in getattr(bs_node, "children", []):
                try:
                    name = getattr(child, "name", None)
                except Exception:
                    name = None
                if not name or name == "[document]":
                    continue
                attrs = getattr(child, "attrs", {}) or {}
                el_id = attrs.get("id")
                classes = attrs.get("class") or []
                item = QTreeWidgetItem([name])
                item.setData(
                    0, Qt.ItemDataRole.UserRole, {"tag": name, "id": el_id, "classes": classes}
                )
                parent_item.addChild(item)
                add_children(child, item)

        add_children(soup, root)
        root.setExpanded(True)

    # ------------------------------------------------------------------
    def _on_item_clicked(self, item: QTreeWidgetItem):  # noqa: D401
        sel = build_selector_for_item(item)
        self.selector_edit.setText(sel)

    # ------------------------------------------------------------------
    def selected_selector(self) -> str:
        return self.selector_edit.text().strip()
