"""Rule Intent Sidebar widget."""

from __future__ import annotations

from typing import Iterable, List, Dict

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QComboBox,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QLabel,
    QHBoxLayout,
)

from gui.ingestion.rule_intent_store import RuleIntent

__all__ = ["RuleIntentSidebar"]


class RuleIntentSidebar(QWidget):
    """Sidebar to view and edit rule intent metadata."""

    saveRequested = pyqtSignal(str, dict)
    resourceChanged = pyqtSignal(str)

    def __init__(self, parent=None):  # noqa: ANN001
        super().__init__(parent)
        self.setObjectName("ruleIntentSidebar")
        self._building = False
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        title = QLabel("Rule Intent")
        title.setObjectName("ruleIntentSidebarTitle")
        layout.addWidget(title)

        self.resource_combo = QComboBox()
        self.resource_combo.currentTextChanged.connect(self._on_resource_changed)  # type: ignore
        layout.addWidget(self.resource_combo)

        layout.addWidget(QLabel("Purpose"))
        self.purpose_edit = QLineEdit()
        layout.addWidget(self.purpose_edit)

        layout.addWidget(QLabel("Assumptions"))
        self.assumptions_edit = QPlainTextEdit()
        self.assumptions_edit.setPlaceholderText("Document assumptions or dependencies...")
        layout.addWidget(self.assumptions_edit)

        layout.addWidget(QLabel("TODO / Follow-ups"))
        self.todo_edit = QPlainTextEdit()
        self.todo_edit.setPlaceholderText("Track TODO items for this resource...")
        layout.addWidget(self.todo_edit)

        button_row = QHBoxLayout()
        self.btn_save = QPushButton("Save Intent")
        self.btn_clear = QPushButton("Clear")
        self.btn_save.clicked.connect(self._emit_save)  # type: ignore
        self.btn_clear.clicked.connect(self.clear_fields)  # type: ignore
        button_row.addWidget(self.btn_save)
        button_row.addWidget(self.btn_clear)
        layout.addLayout(button_row)
        layout.addStretch(1)

    # ------------------------------------------------------------------
    # Data API
    def set_resources(self, resources: Iterable[str]) -> None:
        previous = self.resource_combo.currentText()
        try:
            self._building = True
            self.resource_combo.blockSignals(True)
            self.resource_combo.clear()
            for name in sorted(set(resources)):
                self.resource_combo.addItem(name)
        finally:
            self.resource_combo.blockSignals(False)
            self._building = False
        if previous and previous in [
            self.resource_combo.itemText(i) for i in range(self.resource_combo.count())
        ]:
            self.select_resource(previous)
        elif self.resource_combo.count():
            self.select_resource(self.resource_combo.itemText(0))
        else:
            self.clear_fields()
            self.resourceChanged.emit("")

    def select_resource(self, resource: str) -> None:
        if not resource:
            return
        index = self.resource_combo.findText(resource)
        if index >= 0:
            self.resource_combo.setCurrentIndex(index)
            self._on_resource_changed(resource)

    def current_resource(self) -> str:
        return self.resource_combo.currentText()

    def load_intent(self, intent: RuleIntent) -> None:
        self.purpose_edit.setText(intent.purpose)
        self.assumptions_edit.setPlainText(intent.assumptions)
        self.todo_edit.setPlainText(intent.todo)

    def clear_fields(self) -> None:
        self.purpose_edit.clear()
        self.assumptions_edit.clear()
        self.todo_edit.clear()

    def current_payload(self) -> Dict[str, str]:
        return {
            "purpose": self.purpose_edit.text(),
            "assumptions": self.assumptions_edit.toPlainText(),
            "todo": self.todo_edit.toPlainText(),
        }

    # ------------------------------------------------------------------
    # Event handlers
    def _emit_save(self) -> None:
        resource = self.current_resource()
        payload = self.current_payload()
        if resource:
            self.saveRequested.emit(resource, payload)

    def _on_resource_changed(self, text: str) -> None:
        if self._building:
            return
        self.resourceChanged.emit(text)
