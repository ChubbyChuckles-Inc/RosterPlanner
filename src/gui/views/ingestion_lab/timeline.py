"""Authoring timeline utilities for the ingestion lab panel (Milestone 7.10.A16).

This module provides a pure data model that tracks semantic rule authoring
changes along with a Qt-based mixin that surfaces the history inside the
Ingestion Lab UI. Timeline entries capture resource-level events (adding fields,
changing selectors, etc.), surface a unified diff tooltip, and allow restoring
prior snapshots via a scrub-style slider.
"""

from __future__ import annotations

import difflib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

__all__ = [
    "ChangeEvent",
    "TimelineEntry",
    "AuthoringTimelineModel",
    "AuthoringTimelineMixin",
]


# ---------------------------------------------------------------------------
# Data model helpers


def _mapping_or_empty(value: Any) -> Dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(k): v for k, v in value.items()}
    return {}


def _normalized_repr(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    except Exception:
        return repr(value)


def _sanitize_rules_text(text: str) -> str:
    """Strip inline comment lines and visual builder draft blocks."""

    begin_marker = "# --- Visual Builder Draft BEGIN ---"
    end_marker = "# --- Visual Builder Draft END ---"
    skip_block = False
    lines: List[str] = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n")
        if begin_marker in line:
            skip_block = True
            continue
        if skip_block:
            if end_marker in line:
                skip_block = False
            continue
        stripped = line.lstrip()
        if stripped.startswith("#") and not stripped.startswith("#{"):
            # Treat leading hash as comment (allow literal "#{" edge-case for hashes).
            continue
        lines.append(raw_line)
    sanitized = "\n".join(lines).strip()
    return sanitized


@dataclass(frozen=True)
class ChangeEvent:
    kind: str
    resource: Optional[str] = None
    field: Optional[str] = None
    old: Any = None
    new: Any = None

    def describe(self) -> str:
        if self.kind == "add_resource":
            return f"Added resource '{self.resource}'"
        if self.kind == "remove_resource":
            return f"Removed resource '{self.resource}'"
        if self.kind == "resource_selector":
            return f"Updated selector for '{self.resource}'"
        if self.kind == "resource_item_selector":
            return f"Updated item selector for '{self.resource}'"
        if self.kind == "resource_kind":
            return f"Changed resource kind for '{self.resource}'"
        if self.kind == "resource_columns":
            return f"Updated columns for '{self.resource}'"
        if self.kind == "resource_extends":
            return f"Updated extends for '{self.resource}'"
        if self.kind == "add_field":
            return f"Added field '{self.field}' in '{self.resource}'"
        if self.kind == "remove_field":
            return f"Removed field '{self.field}' from '{self.resource}'"
        if self.kind == "field_selector":
            return f"Updated selector for field '{self.field}' in '{self.resource}'"
        if self.kind == "field_transforms":
            return f"Updated transforms for '{self.field}' in '{self.resource}'"
        if self.kind == "field_macros":
            return f"Updated macros for '{self.field}' in '{self.resource}'"
        if self.kind == "macro_added":
            return f"Added macro '{self.field}'"
        if self.kind == "macro_removed":
            return f"Removed macro '{self.field}'"
        if self.kind == "macro_changed":
            return f"Updated macro '{self.field}'"
        if self.kind == "allow_expressions":
            return "Toggled expression transforms allowance"
        return "Edited rules"

    def detail(self) -> Optional[str]:
        arrow = "→"
        if self.kind in {"resource_selector", "resource_item_selector", "resource_extends"}:
            return f"{self.resource}: {self.old!r} {arrow} {self.new!r}"
        if self.kind == "resource_columns":
            return f"{self.resource} columns: {len(self.old or [])} {arrow} {len(self.new or [])}"
        if self.kind == "resource_kind":
            return f"{self.resource} kind: {self.old!r} {arrow} {self.new!r}"
        if self.kind in {"add_field", "remove_field"}:
            return f"{self.resource}.{self.field}"
        if self.kind == "field_selector":
            return f"{self.resource}.{self.field} selector: {self.old!r} {arrow} {self.new!r}"
        if self.kind == "field_transforms":
            old_len = len(self.old or []) if isinstance(self.old, list) else self.old
            new_len = len(self.new or []) if isinstance(self.new, list) else self.new
            return f"{self.resource}.{self.field} transforms: {old_len} {arrow} {new_len}"
        if self.kind == "field_macros":
            return f"{self.resource}.{self.field} macros: {self.old!r} {arrow} {self.new!r}"
        if self.kind.startswith("macro_"):
            return f"macro {self.field}: {self.old!r} {arrow} {self.new!r}"
        if self.kind == "allow_expressions":
            return f"allow_expressions: {self.old!r} {arrow} {self.new!r}"
        return None


@dataclass(frozen=True)
class TimelineEntry:
    timestamp: datetime
    summary: str
    diff: str
    rendered_text: str
    events: Sequence[ChangeEvent] = field(default_factory=list)
    details: Sequence[str] = field(default_factory=list)

    def tooltip(self, limit: int = 6000) -> str:
        if not self.diff:
            return "No diff available"
        if len(self.diff) <= limit:
            return self.diff
        return self.diff[:limit] + "\n…"


def compute_semantic_events(
    old_rules: Mapping[str, Any], new_rules: Mapping[str, Any]
) -> List[ChangeEvent]:
    events: List[ChangeEvent] = []
    old_resources = _mapping_or_empty(old_rules.get("resources"))
    new_resources = _mapping_or_empty(new_rules.get("resources"))

    old_names = set(old_resources.keys())
    new_names = set(new_resources.keys())

    for name in sorted(new_names - old_names):
        events.append(ChangeEvent("add_resource", resource=name, new=new_resources.get(name)))
    for name in sorted(old_names - new_names):
        events.append(ChangeEvent("remove_resource", resource=name, old=old_resources.get(name)))

    for name in sorted(old_names & new_names):
        old_spec = _mapping_or_empty(old_resources[name])
        new_spec = _mapping_or_empty(new_resources[name])
        if old_spec.get("kind") != new_spec.get("kind"):
            events.append(
                ChangeEvent(
                    "resource_kind",
                    resource=name,
                    old=old_spec.get("kind"),
                    new=new_spec.get("kind"),
                )
            )
        if old_spec.get("selector") != new_spec.get("selector"):
            events.append(
                ChangeEvent(
                    "resource_selector",
                    resource=name,
                    old=old_spec.get("selector"),
                    new=new_spec.get("selector"),
                )
            )
        if old_spec.get("item_selector") != new_spec.get("item_selector"):
            events.append(
                ChangeEvent(
                    "resource_item_selector",
                    resource=name,
                    old=old_spec.get("item_selector"),
                    new=new_spec.get("item_selector"),
                )
            )
        if old_spec.get("extends") != new_spec.get("extends"):
            events.append(
                ChangeEvent(
                    "resource_extends",
                    resource=name,
                    old=old_spec.get("extends"),
                    new=new_spec.get("extends"),
                )
            )
        if old_spec.get("columns") != new_spec.get("columns"):
            events.append(
                ChangeEvent(
                    "resource_columns",
                    resource=name,
                    old=old_spec.get("columns"),
                    new=new_spec.get("columns"),
                )
            )

        old_fields = _mapping_or_empty(old_spec.get("fields"))
        new_fields = _mapping_or_empty(new_spec.get("fields"))
        old_field_names = set(old_fields.keys())
        new_field_names = set(new_fields.keys())

        for fname in sorted(new_field_names - old_field_names):
            events.append(
                ChangeEvent(
                    "add_field",
                    resource=name,
                    field=fname,
                    new=new_fields.get(fname),
                )
            )
        for fname in sorted(old_field_names - new_field_names):
            events.append(
                ChangeEvent(
                    "remove_field",
                    resource=name,
                    field=fname,
                    old=old_fields.get(fname),
                )
            )

        for fname in sorted(old_field_names & new_field_names):
            old_field = _mapping_or_empty(old_fields[fname])
            new_field = _mapping_or_empty(new_fields[fname])
            if old_field.get("selector") != new_field.get("selector"):
                events.append(
                    ChangeEvent(
                        "field_selector",
                        resource=name,
                        field=fname,
                        old=old_field.get("selector"),
                        new=new_field.get("selector"),
                    )
                )
            if old_field.get("transforms") != new_field.get("transforms"):
                events.append(
                    ChangeEvent(
                        "field_transforms",
                        resource=name,
                        field=fname,
                        old=old_field.get("transforms"),
                        new=new_field.get("transforms"),
                    )
                )
            if old_field.get("macros") != new_field.get("macros"):
                events.append(
                    ChangeEvent(
                        "field_macros",
                        resource=name,
                        field=fname,
                        old=old_field.get("macros"),
                        new=new_field.get("macros"),
                    )
                )

    old_macros = _mapping_or_empty(old_rules.get("transform_macros"))
    new_macros = _mapping_or_empty(new_rules.get("transform_macros"))
    old_macro_names = set(old_macros.keys())
    new_macro_names = set(new_macros.keys())

    for macro in sorted(new_macro_names - old_macro_names):
        events.append(ChangeEvent("macro_added", field=macro, new=new_macros.get(macro)))
    for macro in sorted(old_macro_names - new_macro_names):
        events.append(ChangeEvent("macro_removed", field=macro, old=old_macros.get(macro)))
    for macro in sorted(old_macro_names & new_macro_names):
        if old_macros.get(macro) != new_macros.get(macro):
            events.append(
                ChangeEvent(
                    "macro_changed",
                    field=macro,
                    old=old_macros.get(macro),
                    new=new_macros.get(macro),
                )
            )

    allow_old = bool(old_rules.get("allow_expressions", False))
    allow_new = bool(new_rules.get("allow_expressions", False))
    if allow_old != allow_new:
        events.append(ChangeEvent("allow_expressions", old=allow_old, new=allow_new))

    return events


def summarize_events(events: Sequence[ChangeEvent]) -> str:
    if not events:
        return "Edited rules"
    if len(events) == 1:
        return events[0].describe()
    parts = [ev.describe() for ev in events[:2]]
    summary = "; ".join(parts)
    remaining = len(events) - len(parts)
    if remaining > 0:
        summary += f"; +{remaining} more change{'s' if remaining > 1 else ''}"
    return summary


class AuthoringTimelineModel:
    """Track semantic rule edits and produce diff-backed timeline entries."""

    def __init__(self, *, max_entries: int = 50) -> None:
        self._max_entries = max_entries
        self._entries: List[TimelineEntry] = []
        self._last_mapping: Optional[Dict[str, Any]] = None
        self._last_rendered: Optional[str] = None
        self._last_sanitized: str = ""
        self._last_parse_error: Optional[str] = None

    def reset(self, text: str) -> None:
        sanitized, mapping, rendered, error = self._normalize(text)
        self._entries.clear()
        self._last_mapping = mapping
        self._last_rendered = rendered
        self._last_sanitized = sanitized
        self._last_parse_error = error

    def ingest(self, text: str) -> Optional[TimelineEntry]:
        sanitized, mapping, rendered, error = self._normalize(text)
        if error is not None or mapping is None or rendered is None:
            self._last_parse_error = error
            return None
        self._last_parse_error = None
        if self._last_rendered is None or self._last_mapping is None:
            self._last_mapping = mapping
            self._last_rendered = rendered
            self._last_sanitized = sanitized
            return None
        if rendered == self._last_rendered:
            self._last_mapping = mapping
            self._last_rendered = rendered
            self._last_sanitized = sanitized
            return None
        events = compute_semantic_events(self._last_mapping, mapping)
        diff = self._build_diff(self._last_rendered, rendered)
        details = [d for d in (ev.detail() for ev in events) if d]
        entry = TimelineEntry(
            timestamp=datetime.now(),
            summary=summarize_events(events),
            diff=diff,
            rendered_text=rendered,
            events=list(events),
            details=details,
        )
        self._entries.append(entry)
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries :]
        self._last_mapping = mapping
        self._last_rendered = rendered
        self._last_sanitized = sanitized
        return entry

    def entries(self) -> List[TimelineEntry]:
        return list(self._entries)

    @property
    def current_mapping(self) -> Optional[Dict[str, Any]]:
        if self._last_mapping is None:
            return None
        return json.loads(json.dumps(self._last_mapping))

    @property
    def last_parse_error(self) -> Optional[str]:
        return self._last_parse_error

    def _normalize(
        self, text: str
    ) -> tuple[str, Optional[Dict[str, Any]], Optional[str], Optional[str]]:
        sanitized = _sanitize_rules_text(text)
        stripped = sanitized.strip()
        if not stripped:
            sanitized = "{}"
            stripped = sanitized
        try:
            mapping: Dict[str, Any] = json.loads(stripped)
        except json.JSONDecodeError as exc:
            return sanitized, None, None, str(exc)
        rendered = json.dumps(mapping, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        return sanitized, mapping, rendered, None

    @staticmethod
    def _build_diff(prev: str, new: str) -> str:
        prev_lines = prev.splitlines()
        new_lines = new.splitlines()
        diff_iter = difflib.unified_diff(
            prev_lines, new_lines, fromfile="before", tofile="after", lineterm=""
        )
        diff_text = "\n".join(diff_iter)
        return diff_text or ""


# ---------------------------------------------------------------------------
# Qt mixin wiring the model into the Ingestion Lab UI


class AuthoringTimelineMixin:
    _timeline_model: AuthoringTimelineModel
    _timeline_timer: QTimer
    _timeline_pending_text: str
    _timeline_bootstrap: bool
    _timeline_selected_index: Optional[int]

    def _create_authoring_timeline_tab(self) -> QWidget:
        container = QWidget()
        container.setObjectName("ingLabTimelineTab")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(6)

        intro = QLabel(
            "Semantic edit timeline. Scrub through changes, inspect diffs via tooltip, "
            "and restore prior snapshots."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        summary = QLabel("No history captured yet.")
        summary.setObjectName("ingLabTimelineSummary")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setEnabled(False)
        layout.addWidget(slider)

        list_widget = QListWidget()
        list_widget.setObjectName("ingLabTimelineList")
        try:
            list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        except Exception:
            pass
        list_widget.setAlternatingRowColors(True)
        layout.addWidget(list_widget, 1)

        diff_view = QPlainTextEdit()
        diff_view.setObjectName("ingLabTimelineDiff")
        diff_view.setReadOnly(True)
        diff_view.setPlaceholderText("Diff preview will appear here once edits are captured.")
        layout.addWidget(diff_view, 2)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        restore_btn = QPushButton("Restore Snapshot")
        restore_btn.setObjectName("ingLabTimelineRestore")
        restore_btn.setEnabled(False)
        buttons.addWidget(restore_btn)
        layout.addLayout(buttons)

        slider.valueChanged.connect(lambda val: self._select_timeline_entry(int(val), reason="slider"))  # type: ignore[attr-defined]
        list_widget.itemSelectionChanged.connect(self._timeline_on_list_selection)  # type: ignore[attr-defined]
        restore_btn.clicked.connect(self._timeline_restore_selected)  # type: ignore[attr-defined]

        self._timeline_summary_label = summary
        self._timeline_slider = slider
        self._timeline_list = list_widget
        self._timeline_diff_view = diff_view
        self._timeline_restore_btn = restore_btn

        return container

    def _init_authoring_timeline_features(self) -> None:
        self._timeline_model = AuthoringTimelineModel(
            max_entries=int(os.environ.get("RP_ING_TIMELINE_MAX_ENTRIES", "50"))
        )
        self._timeline_timer = QTimer(self)
        self._timeline_timer.setInterval(int(os.environ.get("RP_ING_TIMELINE_DEBOUNCE_MS", "650")))
        self._timeline_timer.setSingleShot(True)
        self._timeline_timer.timeout.connect(self._capture_timeline_snapshot)  # type: ignore[attr-defined]
        self._timeline_pending_text = ""
        self._timeline_bootstrap = True
        self._timeline_selected_index = None
        self._timeline_refresh_ui()

    def _finalize_authoring_timeline_bootstrap(self) -> None:
        text = ""
        try:
            text = self.rule_editor.toPlainText()  # type: ignore[attr-defined]
        except Exception:
            pass
        self._timeline_model.reset(text)
        self._timeline_refresh_ui()
        self._timeline_bootstrap = False

    # ------------------------------------------------------------------
    # Text change hook
    def _on_rule_text_changed(self) -> None:  # type: ignore[override]
        super()._on_rule_text_changed()  # type: ignore[misc]
        if getattr(self, "_timeline_bootstrap", False):
            return
        self._schedule_timeline_snapshot()

    def _schedule_timeline_snapshot(self) -> None:
        if not hasattr(self, "_timeline_timer"):
            return
        try:
            self._timeline_pending_text = self.rule_editor.toPlainText()  # type: ignore[attr-defined]
        except Exception:
            self._timeline_pending_text = ""
        if self._timeline_timer.isActive():
            self._timeline_timer.stop()
        self._timeline_timer.start()

    def _capture_timeline_snapshot(self) -> None:
        text = self._timeline_pending_text
        entry = self._timeline_model.ingest(text)
        if entry:
            self._timeline_refresh_ui(select_latest=True)
            try:
                self._append_log(f"Timeline captured: {entry.summary}")  # type: ignore[attr-defined]
            except Exception:
                pass
        self._timeline_pending_text = ""

    # ------------------------------------------------------------------
    # UI helpers
    def _timeline_refresh_ui(self, *, select_latest: bool = False) -> None:
        if not hasattr(self, "_timeline_list"):
            return
        entries = self._timeline_model.entries()
        count = len(entries)

        self._timeline_list.blockSignals(True)
        self._timeline_list.clear()
        for display_index, entry in enumerate(reversed(entries)):
            chron_idx = count - 1 - display_index
            label = f"{entry.timestamp.strftime('%H:%M:%S')}  {entry.summary}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, chron_idx)
            item.setToolTip(entry.tooltip())
            self._timeline_list.addItem(item)
        self._timeline_list.blockSignals(False)

        self._timeline_slider.blockSignals(True)
        if count <= 1:
            self._timeline_slider.setEnabled(False)
            self._timeline_slider.setRange(0, 0)
            self._timeline_slider.setValue(0)
        else:
            self._timeline_slider.setEnabled(True)
            self._timeline_slider.setRange(0, count - 1)
            if select_latest:
                self._timeline_slider.setValue(count - 1)
            elif self._timeline_selected_index is not None:
                self._timeline_slider.setValue(min(self._timeline_selected_index, count - 1))
        self._timeline_slider.blockSignals(False)

        if not entries:
            self._timeline_selected_index = None
            self._timeline_summary_label.setText("No history captured yet.")
            self._timeline_diff_view.setPlainText("")
            self._timeline_restore_btn.setEnabled(False)
            return

        target_index = (
            count - 1
            if select_latest
            else (
                self._timeline_selected_index
                if self._timeline_selected_index is not None
                else count - 1
            )
        )
        self._select_timeline_entry(target_index, reason="refresh")

    def _select_timeline_entry(self, index: int, *, reason: str = "program") -> None:
        entries = self._timeline_model.entries()
        if not entries:
            return
        index = max(0, min(index, len(entries) - 1))
        self._timeline_selected_index = index
        entry = entries[index]

        if reason != "slider":
            self._timeline_slider.blockSignals(True)
            self._timeline_slider.setValue(index)
            self._timeline_slider.blockSignals(False)

        if reason != "list":
            self._timeline_list.blockSignals(True)
            for row in range(self._timeline_list.count()):
                item = self._timeline_list.item(row)
                if item.data(Qt.ItemDataRole.UserRole) == index:
                    self._timeline_list.setCurrentRow(row)
                    break
            self._timeline_list.blockSignals(False)

        detail_lines = [f"Captured {entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"]
        detail_lines.extend(f"• {line}" for line in entry.details[:5])
        if len(entry.details) > 5:
            detail_lines.append(f"• +{len(entry.details) - 5} additional details")
        summary_text = entry.summary
        if detail_lines:
            summary_text += "\n" + "\n".join(detail_lines)
        self._timeline_summary_label.setText(summary_text)

        diff_text = entry.diff or "(No diff available)"
        if len(diff_text) > 20000:
            diff_text = diff_text[:20000] + "\n…"
        self._timeline_diff_view.setPlainText(diff_text)
        self._timeline_restore_btn.setEnabled(True)

    def _timeline_on_list_selection(self) -> None:
        items = self._timeline_list.selectedItems()
        if not items:
            return
        idx = items[0].data(Qt.ItemDataRole.UserRole)
        if idx is None:
            return
        self._select_timeline_entry(int(idx), reason="list")

    def _timeline_restore_selected(self) -> None:
        if self._timeline_selected_index is None:
            return
        entries = self._timeline_model.entries()
        if self._timeline_selected_index >= len(entries):
            return
        entry = entries[self._timeline_selected_index]
        try:
            self.rule_editor.setPlainText(entry.rendered_text)  # type: ignore[attr-defined]
            self._append_log(f"Timeline restore -> {entry.summary}")  # type: ignore[attr-defined]
        except Exception as exc:
            try:
                self._append_log(f"Timeline restore failed: {exc}")  # type: ignore[attr-defined]
            except Exception:
                pass
