"""Shortcut Cheat Sheet Dialog (Milestone 2.5)

Displays a searchable, categorized list of registered keyboard shortcuts.
Future Enhancements (2.5.1):
 - Conflict detection surface (highlight duplicate sequences)
 - Export / print support
"""

from __future__ import annotations
from typing import List

try:  # pragma: no cover - only executed when PyQt6 present
    from PyQt6.QtWidgets import (
        QDialog,
        QVBoxLayout,
        QLineEdit,
        QTreeWidget,
        QTreeWidgetItem,
        QPushButton,
        QHBoxLayout,
    )
except Exception:  # pragma: no cover
    QDialog = object  # type: ignore

from gui.services.shortcut_registry import global_shortcut_registry, ShortcutEntry


class ShortcutCheatSheetDialog(QDialog):  # pragma: no cover - GUI interaction test optional
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.resize(640, 480)
        self.setObjectName("ShortcutCheatSheetDialog")
        layout = QVBoxLayout(self)
        self.filter_edit = QLineEdit(self)
        self.filter_edit.setPlaceholderText("Filter shortcuts…")
        self.filter_edit.setObjectName("shortcutFilterEdit")
        self.filter_edit.textChanged.connect(self._refresh)  # type: ignore
        layout.addWidget(self.filter_edit)

        self.tree = QTreeWidget(self)
        self.tree.setObjectName("shortcutTree")
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Shortcut", "Description", "Category"])
        layout.addWidget(self.tree)

        btn_row = QHBoxLayout()
        close_btn = QPushButton("Close", self)
        close_btn.setObjectName("shortcutCloseButton")
        close_btn.clicked.connect(self.accept)  # type: ignore
        btn_row.addStretch(1)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._refresh()

    # -------------------------------------------------------------
    def _refresh(self):
        query = self.filter_edit.text().strip().lower() if hasattr(self.filter_edit, "text") else ""
        self.tree.clear()
        entries: List[ShortcutEntry] = global_shortcut_registry.list()
        entries.sort(key=lambda e: (e.category, e.sequence))
        conflicts = global_shortcut_registry.find_conflicts()
        conflict_sequences = {seq for seq in conflicts.keys()}
        for e in entries:
            if query and query not in e.sequence.lower() and query not in e.description.lower():
                continue
            seq_display = e.sequence
            if e.sequence.upper() in conflict_sequences:
                seq_display += "  (conflict)"
            item = QTreeWidgetItem([seq_display, e.description or e.shortcut_id, e.category])  # type: ignore
            if e.sequence.upper() in conflict_sequences:
                item.setToolTip(0, "Multiple shortcuts share this key sequence")  # type: ignore
            self.tree.addTopLevelItem(item)  # type: ignore
        self.tree.resizeColumnToContents(0)  # type: ignore
        self.tree.resizeColumnToContents(1)  # type: ignore
