"""Inline YAML fragment editor dialog for ingestion rules (Milestone 7.10.A15)."""

from __future__ import annotations

import json
from typing import Any, List, Mapping, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from gui.ingestion.rule_schema import RuleError, RuleSet
from gui.ingestion.rule_yaml_fragment import (
    FragmentError,
    PlaceholderSpec,
    apply_fragment,
    generate_placeholders,
    load_rules,
    parse_fragment_yaml,
    prepare_insert_snippet,
    resource_fragment_yaml,
)

__all__ = ["InlineYamlFragmentDialog"]


class GhostTextPlainTextEdit:  # pragma: no cover - thin Qt wrapper (import guard below)
    """Placeholder class replaced with QWidget implementation below."""

    def __init__(self, *_, **__):  # pragma: no cover
        raise RuntimeError("Qt widgets unavailable")


try:  # pragma: no cover - allow headless import during tests
    from PyQt6.QtWidgets import QLabel as _QLabel, QPlainTextEdit

    class GhostOverlayLabel(_QLabel):
        def __init__(self, parent: QPlainTextEdit):
            super().__init__(parent.viewport())
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            self.setStyleSheet("color: rgba(200, 200, 200, 180); font-style: italic;")
            self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            self.hide()

    class GhostTextPlainTextEdit(QPlainTextEdit):  # type: ignore[misc]
        """Text edit that can display ghost placeholder lines within the viewport."""

        def __init__(self, parent=None):
            super().__init__(parent)
            self._ghost_lines: List[str] = []
            self._overlay = GhostOverlayLabel(self)
            self._overlay.setMargin(4)

        def setGhostLines(self, lines: List[str]) -> None:
            self._ghost_lines = lines
            if lines:
                self._overlay.setText("\n".join(lines))
                self._update_overlay_position()
                self._overlay.show()
            else:
                self._overlay.hide()

        def resizeEvent(self, event):  # pragma: no cover - UI path
            super().resizeEvent(event)
            if self._overlay.isVisible():
                self._update_overlay_position()

        def _update_overlay_position(self) -> None:
            if not self._ghost_lines:
                return
            cursor = QTextCursor(self.document())
            cursor.movePosition(QTextCursor.MoveOperation.End)
            rect = self.cursorRect(cursor)
            x = 6
            y = rect.bottom() + 6
            if y + self._overlay.height() > self.viewport().height() - 6:
                y = self.viewport().height() - self._overlay.height() - 6
            if y < 6:
                y = 6
            self._overlay.move(x, y)
            self._overlay.raise_()

except Exception:  # pragma: no cover - headless tests
    pass


class InlineYamlFragmentDialog(QDialog):
    """Dialog allowing inline editing of a single resource's YAML fragment."""

    def __init__(self, rules_text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Inline YAML Fragment Editor")
        self.setModal(True)
        self.resize(720, 540)
        self._rules_mapping = load_rules(rules_text)
        self._resource_names = sorted(self._rules_mapping.get("resources", {}).keys())
        if not self._resource_names:
            raise FragmentError("Rules payload does not contain any resources")
        self._current_resource: Optional[str] = None
        self._current_placeholders: List[PlaceholderSpec] = []
        self._updated_rules_text: Optional[str] = None
        self._build_ui()
        self._populate_resources()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select a resource to edit its YAML fragment."))

        self.resource_combo = QComboBox()
        layout.addWidget(self.resource_combo)

        self.text_edit = GhostTextPlainTextEdit()
        self.text_edit.setObjectName("inlineYamlFragmentEdit")
        self.text_edit.setPlaceholderText("kind: list\nselector: '.example'\n")
        layout.addWidget(self.text_edit, 1)

        self.status_label = QLabel("")
        self.status_label.setObjectName("inlineYamlFragmentStatus")
        self.status_label.setStyleSheet("color: rgb(200,200,200);")
        layout.addWidget(self.status_label)

        button_row = QHBoxLayout()
        self.placeholder_combo = QComboBox()
        self.placeholder_combo.setObjectName("inlineYamlPlaceholderCombo")
        self.placeholder_combo.setToolTip("Select a placeholder snippet to insert")
        self.placeholder_combo.setEnabled(False)
        button_row.addWidget(self.placeholder_combo, 1)
        self.insert_btn = QPushButton("Insert Placeholder")
        button_row.addWidget(self.insert_btn)
        button_row.addStretch(1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        button_row.addWidget(buttons)
        layout.addLayout(button_row)

        self.insert_btn.clicked.connect(self._on_insert_placeholder)  # type: ignore[attr-defined]
        self.resource_combo.currentTextChanged.connect(self._on_resource_changed)  # type: ignore[attr-defined]
        self.text_edit.textChanged.connect(self._on_text_changed)  # type: ignore[attr-defined]
        buttons.accepted.connect(self._on_accept)  # type: ignore[attr-defined]
        buttons.rejected.connect(self.reject)  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    def _populate_resources(self) -> None:
        self.resource_combo.addItems(self._resource_names)
        if self._resource_names:
            self._load_resource(self._resource_names[0])

    def _load_resource(self, name: str) -> None:
        if name not in self._rules_mapping.get("resources", {}):
            return
        self._current_resource = name
        spec = self._rules_mapping["resources"][name]
        yaml_text = resource_fragment_yaml(name, spec, include_name=True)
        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText(yaml_text)
        self.text_edit.blockSignals(False)
        self._update_placeholders(spec)
        self.status_label.setText(f"Editing resource '{name}'")

    def _on_resource_changed(self, name: str) -> None:
        if not name:
            return
        self._load_resource(name)

    def _update_placeholders(self, spec_mapping: Mapping[str, Any]) -> None:
        placeholders = generate_placeholders(spec_mapping)
        self._current_placeholders = placeholders
        self.insert_btn.setEnabled(bool(placeholders))
        self.placeholder_combo.blockSignals(True)
        self.placeholder_combo.clear()
        for spec in placeholders:
            self.placeholder_combo.addItem(spec.display, spec)
        self.placeholder_combo.setEnabled(bool(placeholders))
        if placeholders:
            self.placeholder_combo.setCurrentIndex(0)
        self.placeholder_combo.blockSignals(False)
        ghost_lines = [p.display for p in placeholders[:6]]
        if len(placeholders) > 6:
            ghost_lines.append("…")
        self.text_edit.setGhostLines(ghost_lines)

    def _on_text_changed(self) -> None:
        if not self._current_resource:
            return
        text = self.text_edit.toPlainText()
        try:
            resource_name, spec = parse_fragment_yaml(text, self._current_resource)
            self.status_label.setText(f"Editing resource '{resource_name}'")
            self._update_placeholders(spec)
        except FragmentError as exc:
            self.status_label.setText(f"⚠ {exc}")
            # Keep previous placeholders for stability

    def _on_insert_placeholder(self) -> None:
        if not self._current_placeholders:
            return
        index = self.placeholder_combo.currentIndex()
        spec_data = None
        if index >= 0:
            spec_data = self.placeholder_combo.itemData(index)
        if isinstance(spec_data, PlaceholderSpec):
            spec = spec_data
        else:
            safe_index = min(max(index, 0), len(self._current_placeholders) - 1)
            spec = self._current_placeholders[safe_index]
        existing = self.text_edit.toPlainText()
        snippet = prepare_insert_snippet(spec, existing)
        cursor = self.text_edit.textCursor()
        if cursor.atStart() or not cursor.block().text().strip():
            cursor.insertText(snippet)
        else:
            cursor.insertText("\n" + snippet)
        self.text_edit.setTextCursor(cursor)

    def _on_accept(self) -> None:
        if not self._current_resource:
            return
        fragment_text = self.text_edit.toPlainText()
        try:
            updated_mapping = apply_fragment(
                self._rules_mapping, self._current_resource, fragment_text
            )
            RuleSet.from_mapping(updated_mapping)  # validation pass
        except (FragmentError, RuleError) as exc:
            self.status_label.setText(f"⚠ Cannot apply: {exc}")
            return
        self._updated_rules_text = json.dumps(updated_mapping, indent=2, ensure_ascii=False)
        self.accept()

    def updated_rules_text(self) -> Optional[str]:
        return self._updated_rules_text
