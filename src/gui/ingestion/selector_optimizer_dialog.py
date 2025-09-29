"""Dialog presenting batch selector optimization suggestions."""

from __future__ import annotations

from typing import List, Optional

from PyQt6 import QtCore, QtWidgets

from .selector_optimizer import SelectorOptimizationSuggestion


class SelectorOptimizationDialog(QtWidgets.QDialog):
    """Interactive dialog allowing users to apply selector simplifications."""

    def __init__(
        self,
        suggestions: List[SelectorOptimizationSuggestion],
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent=parent)
        self.setWindowTitle("Batch Selector Optimization")
        self.setModal(True)
        self._suggestions = sorted(
            suggestions,
            key=lambda s: (
                (s.resource_label or "").lower(),
                -s.character_reduction,
                (s.field_label or "").lower(),
            ),
        )
        self._build_ui()
        self._populate_table()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        intro = QtWidgets.QLabel(
            "Review proposed selector simplifications. Deselect any you prefer to keep unchanged."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.table = QtWidgets.QTableWidget(len(self._suggestions), 6, self)
        self.table.setHorizontalHeaderLabels(
            ["Apply", "Field", "Resource", "Original", "Proposed", "Δ chars"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.table)

        buttons_row = QtWidgets.QHBoxLayout()
        self.btn_select_all = QtWidgets.QPushButton("Select All")
        self.btn_select_all.clicked.connect(self._select_all)  # type: ignore[arg-type]
        self.btn_select_none = QtWidgets.QPushButton("Select None")
        self.btn_select_none.clicked.connect(self._select_none)  # type: ignore[arg-type]
        buttons_row.addWidget(self.btn_select_all)
        buttons_row.addWidget(self.btn_select_none)
        buttons_row.addStretch(1)
        layout.addLayout(buttons_row)

        self.details = QtWidgets.QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlaceholderText("Select a row to view details")
        self.details.setMinimumHeight(140)
        layout.addWidget(self.details)

        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _populate_table(self) -> None:
        for row, suggestion in enumerate(self._suggestions):
            checkbox_item = QtWidgets.QTableWidgetItem()
            checkbox_item.setFlags(
                QtCore.Qt.ItemFlag.ItemIsEnabled
                | QtCore.Qt.ItemFlag.ItemIsSelectable
                | QtCore.Qt.ItemFlag.ItemIsUserCheckable
            )
            checkbox_item.setCheckState(QtCore.Qt.CheckState.Checked)
            self.table.setItem(row, 0, checkbox_item)

            field_item = QtWidgets.QTableWidgetItem(suggestion.field_label)
            field_item.setFlags(
                QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled
            )
            self.table.setItem(row, 1, field_item)

            resource_item = QtWidgets.QTableWidgetItem(suggestion.resource_label)
            resource_item.setFlags(
                QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled
            )
            self.table.setItem(row, 2, resource_item)

            original_item = QtWidgets.QTableWidgetItem(suggestion.original_selector)
            original_item.setFlags(
                QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled
            )
            self.table.setItem(row, 3, original_item)

            proposed_item = QtWidgets.QTableWidgetItem(suggestion.optimized_selector)
            proposed_item.setFlags(
                QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled
            )
            self.table.setItem(row, 4, proposed_item)

            delta_item = QtWidgets.QTableWidgetItem(str(suggestion.character_reduction))
            delta_item.setFlags(
                QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled
            )
            self.table.setItem(row, 5, delta_item)
        self.table.resizeColumnsToContents()
        if self._suggestions:
            self.table.selectRow(0)

    def _select_all(self) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None:
                item.setCheckState(QtCore.Qt.CheckState.Checked)

    def _select_none(self) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None:
                item.setCheckState(QtCore.Qt.CheckState.Unchecked)

    def _on_selection_changed(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            self.details.clear()
            return
        row = rows[0].row()
        suggestion = self._suggestions[row]
        summary = [
            f"Field: {suggestion.field_label}",
            f"Resource: {suggestion.resource_label}",
            f"Matches: {suggestion.match_count}",
            f"Character reduction: {suggestion.character_reduction}",
            "",
            f"Original: {suggestion.original_selector}",
            f"Proposed: {suggestion.optimized_selector}",
        ]
        self.details.setPlainText("\n".join(summary))

    def selected_suggestions(self) -> List[SelectorOptimizationSuggestion]:
        chosen: List[SelectorOptimizationSuggestion] = []
        for row, suggestion in enumerate(self._suggestions):
            item = self.table.item(row, 0)
            if item is None:
                continue
            if item.checkState() == QtCore.Qt.CheckState.Checked:
                chosen.append(suggestion)
        return chosen

    def accept(self) -> None:  # pragma: no cover - Qt runtime path
        if not self.selected_suggestions():
            QtWidgets.QMessageBox.warning(
                self,
                "No selections",
                "Select at least one optimization to apply or press Cancel.",
            )
            return
        super().accept()
