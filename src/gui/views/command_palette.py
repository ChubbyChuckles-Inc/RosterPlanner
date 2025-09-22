"""Command Palette Dialog (Milestone 2.4)

A lightweight modal/utility dialog opened via Ctrl+P allowing the user
to quickly execute registered commands. Integrates with the global
command registry. Filtering is incremental as the user types.

Future Enhancements (2.4.x roadmap):
 - Fuzzy scoring (replace simple contains) -- integrates with future scoring util
 - Recently used weighting / section grouping
 - Command categories & icons
 - Async command execution with progress feedback
"""

from __future__ import annotations
from typing import List

try:  # Optional PyQt6 (tests may skip if not installed)
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem
    from PyQt6.QtCore import Qt
except Exception:  # pragma: no cover
    QDialog = object  # type: ignore

from gui.services.command_registry import global_command_registry, CommandEntry

__all__ = ["CommandPaletteDialog"]


class CommandPaletteDialog(QDialog):  # type: ignore[misc]
    """Simple palette UI listing commands matching user query."""

    def __init__(self, parent=None):  # pragma: no cover - UI wiring mostly
        super().__init__(parent)
        if hasattr(self, "setWindowTitle"):
            self.setWindowTitle("Command Palette")
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)  # type: ignore[attr-defined]
        layout = QVBoxLayout(self)
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("Type a command…")
        self.search_edit.textChanged.connect(self._on_text_changed)  # type: ignore[attr-defined]
        self.search_edit.returnPressed.connect(self._activate_selected)  # type: ignore[attr-defined]
        layout.addWidget(self.search_edit)

        self.list_widget = QListWidget(self)
        self.list_widget.itemActivated.connect(lambda _: self._activate_selected())  # type: ignore[attr-defined]
        layout.addWidget(self.list_widget)

        self._refresh_list("")
        self.search_edit.setFocus()

    # Internal -----------------------------------------------------
    def _on_text_changed(self, text: str):  # pragma: no cover trivial
        self._refresh_list(text)

    def _refresh_list(self, query: str):  # pragma: no cover trivial
        self.list_widget.clear()
        entries: List[CommandEntry] = global_command_registry.search(query)
        for entry in entries:
            item = QListWidgetItem(f"{entry.title}    ({entry.command_id})")
            item.setData(Qt.ItemDataRole.UserRole, entry.command_id)  # type: ignore[attr-defined]
            self.list_widget.addItem(item)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _activate_selected(self):  # pragma: no cover trivial
        item = self.list_widget.currentItem()
        if not item:
            return
        command_id = item.data(Qt.ItemDataRole.UserRole)  # type: ignore[attr-defined]
        global_command_registry.execute(command_id)
        self.accept()
