"""Qt dialog for the Dead Field Pruner suggestions."""

from __future__ import annotations

from typing import List

from PyQt6 import QtCore, QtWidgets

from .dead_field_pruner import DeadFieldAction, DeadFieldSuggestion

__all__ = ["DeadFieldPrunerDialog"]


class DeadFieldPrunerDialog(QtWidgets.QDialog):
    """Display dead field suggestions with selectable actions."""

    def __init__(
        self,
        suggestions: List[DeadFieldSuggestion],
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent=parent)
        self.setWindowTitle("Dead Field Pruner")
        self.setModal(True)
        self._suggestions = list(suggestions)
        self._action_widgets: List[QtWidgets.QComboBox] = []
        self._build_ui()
        self._populate_table()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        intro = QtWidgets.QLabel(
            "Fields listed below produced zero non-empty values across the recent preview window."
            " Choose which ones to comment out (moves to inactive stash) or delete entirely."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.table = QtWidgets.QTableWidget(len(self._suggestions), 8, self)
        self.table.setHorizontalHeaderLabels(
            [
                "Apply",
                "Resource",
                "Field",
                "Kind",
                "Window",
                "Evidence",
                "Sample Files",
                "Action",
            ]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        buttons_row = QtWidgets.QHBoxLayout()
        self.btn_select_all = QtWidgets.QPushButton("Select All")
        self.btn_select_all.clicked.connect(self._on_select_all)  # type: ignore[arg-type]
        self.btn_select_none = QtWidgets.QPushButton("Select None")
        self.btn_select_none.clicked.connect(self._on_select_none)  # type: ignore[arg-type]
        buttons_row.addWidget(self.btn_select_all)
        buttons_row.addWidget(self.btn_select_none)
        buttons_row.addStretch(1)
        layout.addLayout(buttons_row)

        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _populate_table(self) -> None:
        self._action_widgets.clear()
        for row, suggestion in enumerate(self._suggestions):
            check_item = QtWidgets.QTableWidgetItem()
            check_item.setFlags(
                QtCore.Qt.ItemFlag.ItemIsEnabled
                | QtCore.Qt.ItemFlag.ItemIsSelectable
                | QtCore.Qt.ItemFlag.ItemIsUserCheckable
            )
            check_item.setCheckState(QtCore.Qt.CheckState.Checked)
            self.table.setItem(row, 0, check_item)

            resource_item = QtWidgets.QTableWidgetItem(suggestion.resource)
            resource_item.setFlags(
                QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled
            )
            self.table.setItem(row, 1, resource_item)

            field_item = QtWidgets.QTableWidgetItem(suggestion.field)
            field_item.setFlags(
                QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled
            )
            self.table.setItem(row, 2, field_item)

            kind_item = QtWidgets.QTableWidgetItem(suggestion.kind)
            kind_item.setFlags(
                QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled
            )
            self.table.setItem(row, 3, kind_item)

            window_item = QtWidgets.QTableWidgetItem(str(suggestion.window))
            window_item.setFlags(
                QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled
            )
            self.table.setItem(row, 4, window_item)

            evidence_text = f"{suggestion.evidence_count()}/{suggestion.preview_count()}"
            evidence_item = QtWidgets.QTableWidgetItem(evidence_text)
            evidence_item.setFlags(
                QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled
            )
            self.table.setItem(row, 5, evidence_item)

            files_text = ", ".join(suggestion.sample_files())
            files_item = QtWidgets.QTableWidgetItem(files_text)
            files_item.setFlags(
                QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled
            )
            files_item.setToolTip(files_text)
            self.table.setItem(row, 6, files_item)

            combo = QtWidgets.QComboBox()
            combo.addItems(["Comment Out", "Delete"])
            self.table.setCellWidget(row, 7, combo)
            self._action_widgets.append(combo)

        self.table.resizeColumnsToContents()
        if self._suggestions:
            self.table.selectRow(0)

    def _on_select_all(self) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None:
                item.setCheckState(QtCore.Qt.CheckState.Checked)

    def _on_select_none(self) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None:
                item.setCheckState(QtCore.Qt.CheckState.Unchecked)

    def selected_actions(self) -> List[DeadFieldAction]:
        actions: List[DeadFieldAction] = []
        for row, suggestion in enumerate(self._suggestions):
            checkbox = self.table.item(row, 0)
            if checkbox is None or checkbox.checkState() != QtCore.Qt.CheckState.Checked:
                continue
            combo = self._action_widgets[row]
            mode = "comment" if combo.currentIndex() == 0 else "delete"
            actions.append(
                DeadFieldAction(resource=suggestion.resource, field=suggestion.field, mode=mode)
            )
        return actions

    def accept(self) -> None:  # pragma: no cover - UI guard
        if not self.selected_actions():
            QtWidgets.QMessageBox.warning(
                self,
                "No selections",
                "Select at least one field to prune or press Cancel.",
            )
            return
        super().accept()
