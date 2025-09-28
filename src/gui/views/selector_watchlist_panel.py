"""Selector Drift Watchlist side panel (Milestone 7.10.A11).

This widget allows power users to pin critical selectors and monitor whether
recent HTML changes caused them to stop matching or to drop sharply in match
count. The panel itself is UI-only; evaluation logic lives in
``selector_watchlist_store`` so it can be tested without a GUI runtime.
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Sequence

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gui.ingestion.rule_schema import ListRule, RuleSet, TableRule
from gui.ingestion.selector_watchlist_store import SelectorWatchEntry, SelectorWatchResult

__all__ = ["SelectorWatchlistPanel"]


class SelectorWatchlistPanel(QWidget):
    """Sidebar widget for managing selector drift watch entries."""

    addWatchRequested = pyqtSignal(str, str, object, int)
    removeRequested = pyqtSignal(list)
    setBaselineRequested = pyqtSignal(list)
    runRequested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("selectorWatchlistPanel")
        self._current_ruleset: Optional[RuleSet] = None
        self._entries: Dict[str, SelectorWatchEntry] = {}
        self._items: Dict[str, QTreeWidgetItem] = {}
        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        title = QLabel("Selector Watchlist")
        title.setObjectName("selectorWatchlistTitle")
        layout.addWidget(title)

        self.resource_combo = QComboBox()
        self.resource_combo.currentTextChanged.connect(self._on_resource_changed)  # type: ignore[arg-type]
        layout.addWidget(self.resource_combo)

        self.target_combo = QComboBox()
        layout.addWidget(self.target_combo)

        threshold_row = QHBoxLayout()
        threshold_row.setContentsMargins(0, 0, 0, 0)
        threshold_row.setSpacing(4)
        threshold_row.addWidget(QLabel("Alert if drop ≥"))
        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(1, 100)
        self.threshold_spin.setValue(50)
        self.threshold_spin.setSuffix(" %")
        threshold_row.addWidget(self.threshold_spin)
        threshold_row.addStretch(1)
        layout.addLayout(threshold_row)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(4)
        self.btn_add = QPushButton("Add")
        self.btn_run = QPushButton("Run Check")
        self.btn_remove = QPushButton("Remove")
        self.btn_baseline = QPushButton("Set Baseline")
        self.btn_add.clicked.connect(self._on_add_clicked)  # type: ignore[arg-type]
        self.btn_run.clicked.connect(lambda: self.runRequested.emit())  # type: ignore[arg-type]
        self.btn_remove.clicked.connect(self._on_remove_clicked)  # type: ignore[arg-type]
        self.btn_baseline.clicked.connect(self._on_set_baseline_clicked)  # type: ignore[arg-type]
        self.btn_remove.setEnabled(False)
        self.btn_baseline.setEnabled(False)
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_run)
        btn_row.addWidget(self.btn_remove)
        btn_row.addWidget(self.btn_baseline)
        layout.addLayout(btn_row)

        self.tree = QTreeWidget()
        self.tree.setObjectName("selectorWatchlistTree")
        self.tree.setColumnCount(9)
        self.tree.setHeaderLabels(
            [
                "Resource",
                "Target",
                "Selector",
                "Baseline",
                "Current",
                "Δ",
                "Drop %",
                "Threshold",
                "Status",
            ]
        )
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)  # type: ignore[arg-type]
        layout.addWidget(self.tree, 1)

        self.status_label = QLabel("No selectors pinned")
        self.status_label.setObjectName("selectorWatchlistStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    # ------------------------------------------------------------------
    def set_ruleset(self, rule_set: Optional[RuleSet]) -> None:
        self._current_ruleset = rule_set
        resources = [] if rule_set is None else rule_set.list_resources()
        previous = self.resource_combo.currentText()
        self.resource_combo.blockSignals(True)
        self.resource_combo.clear()
        for name in resources:
            self.resource_combo.addItem(name)
        self.resource_combo.blockSignals(False)
        if previous and self.resource_combo.findText(previous) >= 0:
            self.resource_combo.setCurrentText(previous)
        elif resources:
            self.resource_combo.setCurrentIndex(0)
        else:
            self.target_combo.clear()
        self._refresh_all_selector_columns()

    def set_entries(self, entries: Sequence[SelectorWatchEntry]) -> None:
        self._entries = {e.identifier(): e for e in entries}
        self.tree.clear()
        self._items = {}
        for entry in entries:
            item = QTreeWidgetItem()
            self._items[entry.identifier()] = item
            item.setData(0, Qt.ItemDataRole.UserRole, entry.identifier())
            self.tree.addTopLevelItem(item)
            self._update_item_display(item, entry, None)
        self.tree.resizeColumnToContents(0)
        self._update_status_label()

    def update_results(self, results: Mapping[str, SelectorWatchResult]) -> None:
        alerts = 0
        for ident, result in results.items():
            entry = self._entries.get(ident)
            item = self._items.get(ident)
            if not entry or not item:
                continue
            entry.last_count = result.current_count
            self._update_item_display(item, entry, result)
            if result.alert:
                alerts += 1
        if results:
            if alerts:
                self.status_label.setText(f"Warnings: {alerts} selector(s) require attention")
            else:
                self.status_label.setText("All monitored selectors look healthy")
        else:
            self._update_status_label()

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def selected_identifiers(self) -> List[str]:
        identifiers: List[str] = []
        for item in self.tree.selectedItems():
            ident = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(ident, str):
                identifiers.append(ident)
        return identifiers

    # ------------------------------------------------------------------
    def _update_status_label(self) -> None:
        if not self._entries:
            self.status_label.setText("No selectors pinned")
        else:
            self.status_label.setText(f"Monitoring {len(self._entries)} selector(s)")

    def _on_add_clicked(self) -> None:
        resource = self.resource_combo.currentText()
        if not resource:
            return
        target_data = self.target_combo.currentData()
        if not isinstance(target_data, tuple) or len(target_data) != 2:
            return
        target_type, target_name = target_data
        threshold = int(self.threshold_spin.value())
        self.addWatchRequested.emit(resource, str(target_type), target_name, threshold)

    def _on_remove_clicked(self) -> None:
        identifiers = self.selected_identifiers()
        if identifiers:
            self.removeRequested.emit(identifiers)

    def _on_set_baseline_clicked(self) -> None:
        identifiers = self.selected_identifiers()
        if identifiers:
            self.setBaselineRequested.emit(identifiers)

    def _on_selection_changed(self) -> None:
        has_selection = bool(self.selected_identifiers())
        self.btn_remove.setEnabled(has_selection)
        self.btn_baseline.setEnabled(has_selection)

    def _on_resource_changed(self, resource: str) -> None:
        self._refresh_target_options(resource)

    def _refresh_target_options(self, resource: Optional[str]) -> None:
        self.target_combo.clear()
        if not resource or not self._current_ruleset:
            return
        rule = self._current_ruleset.resources.get(resource)
        if isinstance(rule, TableRule):
            self.target_combo.addItem("Root Selector", ("root", None))
            return
        if isinstance(rule, ListRule):
            self.target_combo.addItem("Root Selector", ("root", None))
            self.target_combo.addItem("Item Selector", ("item", None))
            for field_name in sorted(rule.fields.keys()):
                self.target_combo.addItem(f"Field: {field_name}", ("field", field_name))
            return
        self.target_combo.addItem("Unsupported resource", ("root", None))

    def _update_item_display(
        self,
        item: QTreeWidgetItem,
        entry: SelectorWatchEntry,
        result: Optional[SelectorWatchResult],
    ) -> None:
        selector = self._selector_for_entry(entry)
        baseline = entry.baseline_count
        current = entry.last_count if entry.last_count is not None else "-"
        delta_text = "-"
        drop_text = "-"
        status = "Pending"
        colour: Optional[QColor] = None
        tooltip = ""
        if result is not None:
            current = result.current_count
            delta_text = f"{result.delta:+d}" if result.delta else "0"
            drop_text = f"{result.drop_percent:.1f}%" if result.baseline_count else "0.0%"
            status = result.status_text()
            colour = (
                QColor("#f07c7c")
                if result.alert
                else (QColor("#a0d468") if result.delta >= 0 else QColor("#f0ad4e"))
            )
            tooltip = result.reason or ""
        item.setText(0, entry.resource)
        item.setText(1, entry.target_label())
        item.setText(2, selector)
        item.setText(3, str(baseline))
        item.setText(4, str(current))
        item.setText(5, delta_text)
        item.setText(6, drop_text)
        item.setText(7, f"{entry.threshold_percent}%")
        item.setText(8, status)
        if colour is not None:
            for col in range(9):
                item.setForeground(col, colour)
        if tooltip:
            for col in range(4):
                item.setToolTip(col, tooltip)
        else:
            for col in range(4):
                item.setToolTip(col, "")

    def _selector_for_entry(self, entry: SelectorWatchEntry) -> str:
        if not self._current_ruleset:
            return "(rule set unavailable)"
        resource = self._current_ruleset.resources.get(entry.resource)
        if resource is None:
            return "(resource missing)"
        if isinstance(resource, TableRule):
            return resource.selector
        if isinstance(resource, ListRule):
            if entry.target_type == "root":
                return resource.selector
            if entry.target_type == "item":
                return resource.item_selector
            if entry.target_type == "field" and entry.target_name:
                field = resource.fields.get(entry.target_name)
                if field:
                    return field.selector
                return "(field missing)"
        return "(unsupported)"

    def _refresh_all_selector_columns(self) -> None:
        for ident, item in self._items.items():
            entry = self._entries.get(ident)
            if not entry:
                continue
            selector = self._selector_for_entry(entry)
            item.setText(2, selector)
