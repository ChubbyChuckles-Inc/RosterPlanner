"""Keyboard macro shortcut templates (Milestone 7.10.A21).

This module provides a lightweight store for transform chain templates that can
be bound to keyboard shortcuts inside the Ingestion Lab. Templates are stored in
``QSettings`` (with an in-memory fallback for headless tests) and exposed via a
Qt dialog for easy assignment when PyQt6 is available.  The pure-Python helper
APIs are unit tested so the feature can be validated without requiring a GUI
runtime.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from gui.ingestion.rule_schema import RuleSet, TransformSpec

__all__ = [
    "MacroShortcutTemplate",
    "load_templates",
    "save_templates",
    "extract_templates_from_ruleset",
    "clear_test_store",
    "MacroShortcutDialog",
]

_SETTINGS_ORG = "RosterPlanner"
_SETTINGS_APP = "IngestionLab"
_SETTINGS_KEY = "macro_shortcuts_v1"
_FALLBACK_SETTINGS: Dict[str, Any] = {}
_SIMPLE_TRANSFORMS = {"trim", "collapse_ws", "to_number"}


class _SettingsAdapter:
    """Small wrapper used for QSettings fallback in test environments."""

    def __init__(self, backend: Dict[str, Any]) -> None:
        self._backend = backend

    def value(self, key: str, default: Any = None) -> Any:
        return self._backend.get(key, default)

    def setValue(self, key: str, value: Any) -> None:
        self._backend[key] = value


def _use_fallback_settings() -> bool:
    if os.environ.get("RP_TEST_MODE"):
        return True
    return False


def _get_settings():
    if _use_fallback_settings():
        return _SettingsAdapter(_FALLBACK_SETTINGS)
    try:  # pragma: no cover - import guard for environments without PyQt6
        from PyQt6.QtCore import QSettings
    except Exception:
        return _SettingsAdapter(_FALLBACK_SETTINGS)
    try:
        return QSettings(_SETTINGS_ORG, _SETTINGS_APP)
    except Exception:  # pragma: no cover - defensive guard when QSettings backend fails
        return _SettingsAdapter(_FALLBACK_SETTINGS)


def clear_test_store() -> None:
    """Reset the in-memory settings store used during tests."""

    _FALLBACK_SETTINGS.clear()


def _normalize_chain(chain: Iterable[Any]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for item in chain:
        if isinstance(item, str):
            kind = item.strip()
            if not kind:
                continue
            normalized.append({"kind": kind})
            continue
        if isinstance(item, Mapping):
            kind = item.get("kind")
            if not isinstance(kind, str) or not kind:
                continue
            entry: Dict[str, Any] = {"kind": kind}
            fmts = item.get("formats")
            if isinstance(fmts, Iterable) and not isinstance(fmts, (str, bytes)):
                fmts_list = [f for f in fmts if isinstance(f, str) and f]
                if fmts_list:
                    entry["formats"] = fmts_list
            code = item.get("code")
            if isinstance(code, str) and code.strip():
                entry["code"] = code
            normalized.append(entry)
    return normalized


def _spec_to_template_item(spec: TransformSpec) -> Dict[str, Any]:
    mapping = spec.to_mapping()
    if isinstance(mapping, str):
        return {"kind": mapping}
    kind = mapping.get("kind") if isinstance(mapping, Mapping) else None
    if not isinstance(kind, str) or not kind:
        return {"kind": ""}
    entry: Dict[str, Any] = {"kind": kind}
    if mapping.get("formats"):
        entry["formats"] = list(mapping.get("formats", []))
    if mapping.get("code") is not None:
        entry["code"] = mapping.get("code")
    return entry


@dataclass
class MacroShortcutTemplate:
    """Represents a reusable transform chain template bound to a shortcut."""

    name: str
    chain: List[Dict[str, Any]] = field(default_factory=list)
    sequence: str = ""
    source: str = "custom"
    description: Optional[str] = None

    def summary(self, limit: int = 6) -> str:
        kinds = [item.get("kind", "?") for item in self.chain if isinstance(item, Mapping)]
        if not kinds:
            return "—"
        if len(kinds) > limit:
            kinds = kinds[:limit] + ["…"]
        return " \u2192 ".join(kinds)

    def render_snippet(self, indent: str = "") -> str:
        if not self.chain:
            return ""
        payload: List[Any] = []
        for item in self.chain:
            if not isinstance(item, Mapping):
                continue
            kind = item.get("kind")
            if not isinstance(kind, str) or not kind:
                continue
            if kind in _SIMPLE_TRANSFORMS and all(k in {"kind"} for k in item.keys()):
                payload.append(kind)
            else:
                spec: Dict[str, Any] = {"kind": kind}
                if item.get("formats"):
                    spec["formats"] = list(item.get("formats", []))
                if item.get("code") is not None:
                    spec["code"] = item.get("code")
                payload.append(spec)
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        if indent:
            return "\n".join(indent + line if line else line for line in text.splitlines())
        return text

    def to_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "name": self.name,
            "chain": [dict(item) for item in self.chain],
            "sequence": self.sequence,
            "source": self.source,
        }
        if self.description:
            payload["description"] = self.description
        return payload

    def clone(self) -> "MacroShortcutTemplate":
        return MacroShortcutTemplate(
            name=self.name,
            chain=[dict(item) for item in self.chain],
            sequence=self.sequence,
            source=self.source,
            description=self.description,
        )

    @staticmethod
    def from_payload(payload: Mapping[str, Any]) -> "MacroShortcutTemplate":
        name = str(payload.get("name", "")).strip()
        if not name:
            raise ValueError("MacroShortcutTemplate payload missing name")
        chain = _normalize_chain(payload.get("chain", []))
        sequence = str(payload.get("sequence", "") or "")
        source = str(payload.get("source", "custom") or "custom")
        description = payload.get("description")
        if description is not None:
            description = str(description)
        return MacroShortcutTemplate(
            name=name,
            chain=chain,
            sequence=sequence,
            source=source,
            description=description or None,
        )


def load_templates() -> List[MacroShortcutTemplate]:
    settings = _get_settings()
    raw = settings.value(_SETTINGS_KEY)
    if not raw:
        return []
    payload: Any
    if isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except Exception:
            return []
    else:
        payload = raw
    templates: List[MacroShortcutTemplate] = []
    if isinstance(payload, list):
        for entry in payload:
            if not isinstance(entry, Mapping):
                continue
            try:
                templates.append(MacroShortcutTemplate.from_payload(entry))
            except Exception:
                continue
    return templates


def save_templates(templates: Sequence[MacroShortcutTemplate]) -> None:
    serialisable = [tpl.to_payload() for tpl in templates]
    settings = _get_settings()
    settings.setValue(_SETTINGS_KEY, json.dumps(serialisable, ensure_ascii=False))


def extract_templates_from_ruleset(rule_set: RuleSet) -> List[MacroShortcutTemplate]:
    templates: List[MacroShortcutTemplate] = []
    for name in sorted(rule_set.transform_macros.keys()):
        chain = rule_set.transform_macros[name]
        normalized = [_spec_to_template_item(spec) for spec in chain]
        templates.append(
            MacroShortcutTemplate(
                name=name,
                chain=normalized,
                sequence="",
                source="ruleset",
                description="Transform macro from current rule set",
            )
        )
    return templates


# ---------------------------------------------------------------------------
# Qt Dialog (optional)

try:  # pragma: no cover - UI layer exercised in integration tests
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QKeySequence
    from PyQt6.QtWidgets import (
        QAbstractItemView,
        QDialog,
        QDialogButtonBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPlainTextEdit,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
        QKeySequenceEdit,
    )
    from gui.components.chrome_dialog import ChromeDialog
except Exception:  # pragma: no cover - headless environments
    MacroShortcutDialog = None  # type: ignore
else:
    _DialogBase = ChromeDialog if ChromeDialog is not None else QDialog

    def _is_dialog_accepted(result: int) -> bool:
        return result == int(QDialog.DialogCode.Accepted)

    class _ShortcutCaptureDialog(_DialogBase):  # pragma: no cover - simple helper dialog
        def __init__(self, parent: Optional[QWidget] = None, current: str = "") -> None:
            title = "Assign Shortcut"
            if ChromeDialog is not None:
                super().__init__(parent, title=title)
            else:
                super().__init__(parent)
                self.setWindowTitle(title)
            layout = (
                self.content_layout()  # type: ignore[attr-defined]
                if hasattr(self, "content_layout")
                else QVBoxLayout(self)
            )
            layout.setContentsMargins(12, 12, 12, 12)
            info = QLabel("Press the desired key combination, then choose Save.")
            info.setWordWrap(True)
            layout.addWidget(info)
            self._edit = QKeySequenceEdit()
            if current:
                self._edit.setKeySequence(QKeySequence(current))
            layout.addWidget(self._edit)
            btns = QDialogButtonBox()
            btns.addButton("Save", QDialogButtonBox.ButtonRole.AcceptRole)
            btns.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
            btns.accepted.connect(self.accept)
            btns.rejected.connect(self.reject)
            layout.addWidget(btns)

        def captured(self) -> str:
            seq = self._edit.keySequence()
            return seq.toString(QKeySequence.SequenceFormat.PortableText).strip()

    class _CustomTemplateDialog(_DialogBase):  # pragma: no cover - simple helper dialog
        def __init__(self, used_names: Sequence[str], parent: Optional[QWidget] = None) -> None:
            title = "New Transform Template"
            if ChromeDialog is not None:
                super().__init__(parent, title=title)
            else:
                super().__init__(parent)
                self.setWindowTitle(title)
            self._used = {name.lower() for name in used_names}
            self._template: Optional[MacroShortcutTemplate] = None
            layout = (
                self.content_layout()  # type: ignore[attr-defined]
                if hasattr(self, "content_layout")
                else QVBoxLayout(self)
            )
            layout.setContentsMargins(12, 12, 12, 12)

            name_row = QHBoxLayout()
            name_row.addWidget(QLabel("Name:"))
            self._name = QLineEdit()
            name_row.addWidget(self._name, 1)
            layout.addLayout(name_row)

            seq_row = QHBoxLayout()
            seq_row.addWidget(QLabel("Shortcut:"))
            self._seq = QKeySequenceEdit()
            seq_row.addWidget(self._seq, 1)
            layout.addLayout(seq_row)

            layout.addWidget(QLabel("Transforms JSON (list of transform specs):"))
            self._chain = QPlainTextEdit('[\n  {"kind": "trim"}\n]')
            self._chain.setMinimumHeight(120)
            layout.addWidget(self._chain)

            hint = QLabel(
                "Tip: simple transforms (trim, collapse_ws, to_number) may be provided as strings;"
                " complex transforms require a mapping with additional parameters."
            )
            hint.setWordWrap(True)
            layout.addWidget(hint)

            btns = QDialogButtonBox()
            btns.addButton("Create", QDialogButtonBox.ButtonRole.AcceptRole)
            btns.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
            btns.accepted.connect(self._on_accept)
            btns.rejected.connect(self.reject)
            layout.addWidget(btns)

        def _on_accept(self) -> None:
            name = self._name.text().strip()
            if not name:
                QMessageBox.warning(self, "Missing name", "Please enter a template name.")
                return
            if name.lower() in self._used:
                QMessageBox.warning(
                    self,
                    "Name in use",
                    "A template with this name already exists. Choose another name.",
                )
                return
            seq = self._seq.keySequence().toString(QKeySequence.SequenceFormat.PortableText).strip()
            if not seq:
                QMessageBox.warning(self, "Missing shortcut", "Please record a shortcut.")
                return
            try:
                payload = json.loads(self._chain.toPlainText())
            except Exception:
                QMessageBox.warning(self, "Invalid JSON", "Transforms JSON could not be parsed.")
                return
            chain = _normalize_chain(payload if isinstance(payload, list) else [])
            if not chain:
                QMessageBox.warning(
                    self,
                    "Invalid transforms",
                    "Provide at least one transform specification.",
                )
                return
            self._template = MacroShortcutTemplate(
                name=name,
                chain=chain,
                sequence=seq,
                source="custom",
            )
            super().accept()

        def template(self) -> Optional[MacroShortcutTemplate]:
            return self._template

    class MacroShortcutDialog(_DialogBase):  # pragma: no cover - interactive UI tested in GUI layer
        def __init__(
            self,
            stored: Sequence[MacroShortcutTemplate],
            suggestions: Sequence[MacroShortcutTemplate] | None = None,
            parent: Optional[QWidget] = None,
        ) -> None:
            title = "Keyboard Macro Shortcuts"
            if ChromeDialog is not None:
                super().__init__(parent, title=title)
            else:
                super().__init__(parent)
                self.setWindowTitle(title)
            self.resize(760, 400)

            self._templates: List[MacroShortcutTemplate] = []
            self._templates_by_name: Dict[str, MacroShortcutTemplate] = {}
            self._merge_templates(stored, suggestions or [])

            layout = (
                self.content_layout()  # type: ignore[attr-defined]
                if hasattr(self, "content_layout")
                else QVBoxLayout(self)
            )
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(8)

            self._warning_label = QLabel("")
            self._warning_label.setWordWrap(True)
            self._warning_label.setStyleSheet("color:#c77;")
            self._warning_label.hide()
            layout.addWidget(self._warning_label)

            self._table = QTableWidget()
            self._table.setColumnCount(3)
            self._table.setHorizontalHeaderLabels(["Shortcut", "Template", "Steps"])
            self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            self._table.verticalHeader().setVisible(False)
            self._table.horizontalHeader().setStretchLastSection(True)
            layout.addWidget(self._table, 1)

            btn_row = QHBoxLayout()
            self._btn_assign = QPushButton("Assign Shortcut")
            self._btn_clear = QPushButton("Clear")
            self._btn_add = QPushButton("Add Template")
            self._btn_remove = QPushButton("Remove Template")
            btn_row.addWidget(self._btn_assign)
            btn_row.addWidget(self._btn_clear)
            btn_row.addStretch(1)
            btn_row.addWidget(self._btn_add)
            btn_row.addWidget(self._btn_remove)
            layout.addLayout(btn_row)

            self._btn_assign.clicked.connect(self._on_assign)
            self._btn_clear.clicked.connect(self._on_clear)
            self._btn_add.clicked.connect(self._on_add)
            self._btn_remove.clicked.connect(self._on_remove)

            self._buttons = QDialogButtonBox()
            self._buttons.addButton("Save", QDialogButtonBox.ButtonRole.AcceptRole)
            self._buttons.addButton("Close", QDialogButtonBox.ButtonRole.RejectRole)
            self._buttons.accepted.connect(self.accept)
            self._buttons.rejected.connect(self.reject)
            layout.addWidget(self._buttons)

            self._refresh_table()

        # ------------------------------------------------------------------
        def set_warning(self, message: str) -> None:
            if not message:
                self._warning_label.hide()
                return
            self._warning_label.setText(message)
            self._warning_label.show()

        def _merge_templates(
            self,
            stored: Sequence[MacroShortcutTemplate],
            suggestions: Sequence[MacroShortcutTemplate],
        ) -> None:
            for tpl in stored:
                clone = tpl.clone()
                self._templates.append(clone)
                self._templates_by_name[clone.name] = clone
            for tpl in suggestions:
                existing = self._templates_by_name.get(tpl.name)
                if existing:
                    existing.chain = [dict(item) for item in tpl.chain]
                    existing.source = tpl.source
                    if tpl.description:
                        existing.description = tpl.description
                else:
                    clone = tpl.clone()
                    self._templates.append(clone)
                    self._templates_by_name[clone.name] = clone

        def _refresh_table(self, select_name: Optional[str] = None) -> None:
            self._templates.sort(key=lambda t: t.name.lower())
            self._table.setRowCount(len(self._templates))
            for row, tpl in enumerate(self._templates):
                shortcut_item = QTableWidgetItem(tpl.sequence or "—")
                label = tpl.name
                if tpl.source == "ruleset":
                    label += " (rule macro)"
                elif tpl.source == "custom":
                    label += " (custom)"
                template_item = QTableWidgetItem(label)
                steps_item = QTableWidgetItem(tpl.summary())
                for item in (shortcut_item, template_item, steps_item):
                    flags = item.flags()
                    item.setFlags(flags & ~Qt.ItemFlag.ItemIsEditable)
                steps_item.setToolTip(
                    "Transforms: " + ", ".join(item.get("kind", "?") for item in tpl.chain)
                    if tpl.chain
                    else "Transforms: none"
                )
                self._table.setItem(row, 0, shortcut_item)
                self._table.setItem(row, 1, template_item)
                self._table.setItem(row, 2, steps_item)
            self._table.resizeColumnsToContents()
            if select_name:
                for row, tpl in enumerate(self._templates):
                    if tpl.name == select_name:
                        self._table.selectRow(row)
                        break
            elif self._templates:
                self._table.selectRow(0)

        def _current_template(self) -> Optional[MacroShortcutTemplate]:
            row = self._table.currentRow()
            if row < 0 or row >= len(self._templates):
                return None
            return self._templates[row]

        def _ensure_unique_sequence(self, sequence: str, current: MacroShortcutTemplate) -> bool:
            seq_norm = sequence.upper()
            for tpl in self._templates:
                if tpl is current or not tpl.sequence:
                    continue
                if tpl.sequence.upper() == seq_norm:
                    QMessageBox.warning(
                        self,
                        "Shortcut in use",
                        f"The shortcut {sequence} is already assigned to '{tpl.name}'.",
                    )
                    return False
            return True

        def _on_assign(self) -> None:
            tpl = self._current_template()
            if not tpl:
                QMessageBox.information(self, "Select template", "Choose a template first.")
                return
            dialog = _ShortcutCaptureDialog(self, tpl.sequence)
            if not _is_dialog_accepted(dialog.exec()):
                return
            sequence = dialog.captured()
            if not sequence:
                return
            if not self._ensure_unique_sequence(sequence, tpl):
                return
            tpl.sequence = sequence
            self._refresh_table(select_name=tpl.name)

        def _on_clear(self) -> None:
            tpl = self._current_template()
            if not tpl:
                return
            tpl.sequence = ""
            self._refresh_table(select_name=tpl.name)

        def _on_add(self) -> None:
            dialog = _CustomTemplateDialog([t.name for t in self._templates], self)
            if not _is_dialog_accepted(dialog.exec()):
                return
            new_tpl = dialog.template()
            if not new_tpl:
                return
            if not self._ensure_unique_sequence(new_tpl.sequence, new_tpl):
                return
            self._templates.append(new_tpl)
            self._templates_by_name[new_tpl.name] = new_tpl
            self._refresh_table(select_name=new_tpl.name)

        def _on_remove(self) -> None:
            tpl = self._current_template()
            if not tpl:
                return
            if tpl.source != "custom":
                QMessageBox.information(
                    self,
                    "Cannot remove",
                    "Only custom templates can be removed. Clear the shortcut to unbind rule macros.",
                )
                return
            self._templates.remove(tpl)
            self._templates_by_name.pop(tpl.name, None)
            self._refresh_table()

        def persisted_templates(self) -> List[MacroShortcutTemplate]:
            retained = [tpl.clone() for tpl in self._templates if tpl.sequence]
            retained.sort(key=lambda t: t.name.lower())
            return retained
