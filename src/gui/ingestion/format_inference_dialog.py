"""Dialog for selecting inferred format transforms."""

from __future__ import annotations

from typing import Optional, Tuple

from PyQt6 import QtCore, QtWidgets

from .format_inference import (
    DateFormatSuggestion,
    FormatInferenceResult,
    NumberFormatSuggestion,
)

SuggestionPayload = Tuple[str, object]


class FormatInferenceDialog(QtWidgets.QDialog):
    """Present inferred date/number formats and capture the user's selection."""

    def __init__(
        self,
        samples: list[str],
        inference: FormatInferenceResult,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent=parent)
        self.setWindowTitle("Apply inferred formats")
        self.setModal(True)
        self._samples = samples
        self._inference = inference
        self.selected_suggestion: Optional[SuggestionPayload] = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        info_label = QtWidgets.QLabel(
            "Select the transform suggestion that best matches the sampled values."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        self._tree = QtWidgets.QTreeWidget(self)
        self._tree.setHeaderLabels(["Kind", "Summary", "Confidence"])
        self._tree.setRootIsDecorated(False)
        self._tree.setAlternatingRowColors(True)
        self._tree.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self._tree.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self._tree)

        details_group = QtWidgets.QGroupBox("Sample values")
        details_layout = QtWidgets.QVBoxLayout(details_group)
        self._samples_list = QtWidgets.QListWidget(details_group)
        for sample in self._samples[:20]:
            self._samples_list.addItem(sample)
        details_layout.addWidget(self._samples_list)

        layout.addWidget(details_group)

        self._details_edit = QtWidgets.QPlainTextEdit(self)
        self._details_edit.setReadOnly(True)
        self._details_edit.setPlaceholderText("Select a suggestion to review details.")
        layout.addWidget(self._details_edit)

        self._button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self._button_box.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        layout.addWidget(self._button_box)

        self._tree.itemSelectionChanged.connect(self._on_selection_changed)
        self._tree.itemDoubleClicked.connect(self._accept_on_double_click)
        self._button_box.accepted.connect(self.accept)
        self._button_box.rejected.connect(self.reject)

        self._populate_tree()

    def _populate_tree(self) -> None:
        self._tree.clear()
        if self._inference.number:
            self._add_number_item(self._inference.number)
        for suggestion in self._inference.dates:
            self._add_date_item(suggestion)
        if self._tree.topLevelItemCount() > 0:
            self._tree.resizeColumnToContents(0)
            self._tree.resizeColumnToContents(2)
        else:
            empty_item = QtWidgets.QTreeWidgetItem(["No suggestions", "", ""])
            empty_item.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
            self._tree.addTopLevelItem(empty_item)

    def _add_number_item(self, suggestion: NumberFormatSuggestion) -> None:
        item = QtWidgets.QTreeWidgetItem(
            [
                "Number",
                suggestion.summary(),
                f"{suggestion.confidence:.0%}",
            ]
        )
        item.setData(0, QtCore.Qt.ItemDataRole.UserRole, ("number", suggestion))
        self._tree.addTopLevelItem(item)

    def _add_date_item(self, suggestion: DateFormatSuggestion) -> None:
        item = QtWidgets.QTreeWidgetItem(
            [
                "Date",
                suggestion.summary(),
                f"{suggestion.confidence:.0%}",
            ]
        )
        item.setData(0, QtCore.Qt.ItemDataRole.UserRole, ("date", suggestion))
        self._tree.addTopLevelItem(item)

    def _on_selection_changed(self) -> None:
        items = self._tree.selectedItems()
        ok_button = self._button_box.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        if not items:
            ok_button.setEnabled(False)
            self._details_edit.clear()
            self.selected_suggestion = None
            return
        item = items[0]
        payload = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if not payload:
            ok_button.setEnabled(False)
            self._details_edit.clear()
            self.selected_suggestion = None
            return
        ok_button.setEnabled(True)
        self.selected_suggestion = payload
        self._details_edit.setPlainText(self._format_details(payload))

    def _format_details(self, payload: SuggestionPayload) -> str:
        kind, suggestion = payload
        if kind == "number":
            assert isinstance(suggestion, NumberFormatSuggestion)
            lines = ["Number format inference", "-------------------------"]
            lines.append(f"Locale: {suggestion.locale or 'Not specified'}")
            lines.append(f"Decimal separator: {suggestion.decimal_separator or 'auto'}")
            lines.append(f"Grouping separator: {suggestion.grouping_separator or 'auto'}")
            lines.append(f"Confidence: {suggestion.confidence:.0%}")
            lines.append("Preview values:")
            lines.extend(f"  - {value}" for value in suggestion.normalized_samples)
            return "\n".join(lines)
        assert isinstance(suggestion, DateFormatSuggestion)
        lines = ["Date format inference", "----------------------"]
        lines.append(f"Formats: {', '.join(suggestion.formats)}")
        lines.append(f"Confidence: {suggestion.confidence:.0%}")
        lines.append(f"Example ISO value: {suggestion.example_iso}")
        return "\n".join(lines)

    def _accept_on_double_click(self, item: QtWidgets.QTreeWidgetItem) -> None:
        payload = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if payload:
            self.selected_suggestion = payload
            self.accept()

    def accept(self) -> None:  # pragma: no cover - Qt dialog wiring
        if self.selected_suggestion is None:
            return
        super().accept()
