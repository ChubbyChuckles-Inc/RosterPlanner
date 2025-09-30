"""Row diff viewer widget for the Database panel (Milestone 7.11.10).

The widget lets users pick two rows from the current preview result set
and compares them column-by-column. Differences are highlighted inline
while unchanged values are summarized succinctly. The viewer relies on
the preview data already fetched by :class:`LazyDataPreviewModel` to
ensure comparisons stay scoped to the active filter context.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple, Union

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import (
    QComboBox,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

try:  # pragma: no cover - fallback when theme mixin unavailable in tests
    from gui.components.theme_aware import ThemeAwareMixin  # type: ignore
except Exception:  # pragma: no cover

    class ThemeAwareMixin:  # type: ignore
        """Fallback mixin used when theming infrastructure is unavailable."""

        def apply_theme(self) -> None:  # noqa: D401 - compatibility stub
            """No-op fallback when theming infrastructure is absent."""


from gui.services.schema_introspection_service import TableInfo
from gui.viewmodels.data_preview_model import DataPreviewPage

__all__ = ["RowDiffViewer", "RowDiffViewerWidget"]


@dataclass(frozen=True)
class _RowCacheEntry:
    """Cached representation of a preview row for combo box binding."""

    index: int
    label: str
    row: Tuple[object, ...]


class RowDiffViewer(QWidget, ThemeAwareMixin):
    """Render inline value diffs between two preview rows."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialise the diff viewer widget and combo boxes."""

        super().__init__(parent)
        self.setObjectName("dbRowDiffViewer")
        self._table: Optional[str] = None
        self._table_info: Optional[TableInfo] = None
        self._page: Optional[DataPreviewPage] = None
        self._rows: List[_RowCacheEntry] = []
        self._updating = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = QLabel("Row diff viewer")
        header.setObjectName("dbRowDiffHeader")
        layout.addWidget(header)

        self._base_selector = QComboBox(self)
        self._base_selector.setObjectName("dbRowDiffBase")
        self._base_selector.currentIndexChanged.connect(self._on_selection_changed)  # type: ignore
        layout.addWidget(self._base_selector)

        self._compare_selector = QComboBox(self)
        self._compare_selector.setObjectName("dbRowDiffCompare")
        self._compare_selector.currentIndexChanged.connect(self._on_selection_changed)  # type: ignore
        layout.addWidget(self._compare_selector)

        self._diff_view = QPlainTextEdit(self)
        self._diff_view.setObjectName("dbRowDiffOutput")
        self._diff_view.setReadOnly(True)
        self._diff_view.setMinimumHeight(120)
        try:  # pragma: no cover - depends on platform font availability
            font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
            self._diff_view.setFont(font)
        except Exception:
            pass
        layout.addWidget(self._diff_view)

        self.clear("Select two rows to compare differences.")

    # ------------------------------------------------------------------
    def set_context(self, table: str, table_info: Optional[TableInfo]) -> None:
        """Update the active table context."""

        self._table = table
        self._table_info = table_info
        if table_info is None:
            self.show_unavailable("Row diff viewer unavailable (no schema info).")
        elif self._page is not None:
            self.update_from_preview(self._page)

    def update_from_preview(self, page: Optional[DataPreviewPage]) -> None:
        """Refresh selector choices using the latest preview page."""

        self._page = page
        self._rows.clear()
        self._updating = True
        try:
            self._base_selector.blockSignals(True)
            self._compare_selector.blockSignals(True)
            self._base_selector.clear()
            self._compare_selector.clear()
            if page is None or not page.rows:
                self._disable_selectors("No rows available to diff. Adjust filters or ingest data.")
                return
            columns = page.columns
            for idx, row in enumerate(page.rows):
                label = self._build_row_label(idx, columns, row)
                entry = _RowCacheEntry(index=idx, label=label, row=row)
                self._rows.append(entry)
                self._base_selector.addItem(label, idx)
                self._compare_selector.addItem(label, idx)
            if len(self._rows) < 2:
                self._disable_selectors("Need at least two rows to compute diffs.")
                return
            self._enable_selectors()
            self._base_selector.setCurrentIndex(0)
            self._compare_selector.setCurrentIndex(1)
        finally:
            self._base_selector.blockSignals(False)
            self._compare_selector.blockSignals(False)
            self._updating = False
        self._update_diff()

    def clear(self, message: str = "") -> None:
        """Reset selectors and display the provided message."""

        self._rows.clear()
        self._disable_selectors(message)

    def show_unavailable(self, message: str) -> None:
        """Display an unavailable state message."""

        self.clear(message)
        self._page = None

    # ------------------------------------------------------------------
    def _disable_selectors(self, message: str) -> None:
        """Disable selection widgets and display *message*."""

        self._base_selector.clear()
        self._compare_selector.clear()
        self._base_selector.setEnabled(False)
        self._compare_selector.setEnabled(False)
        self._diff_view.setPlainText(message)

    def _enable_selectors(self) -> None:
        """Enable both selectors for user interaction."""

        self._base_selector.setEnabled(True)
        self._compare_selector.setEnabled(True)

    def _on_selection_changed(self, _index: int) -> None:
        """React to combo box selection changes."""

        if self._updating:
            return
        self._update_diff()

    def _update_diff(self) -> None:
        """Compute and render the diff for the currently selected rows."""

        if not self._rows:
            return
        base_entry = self._get_selected_entry(self._base_selector.currentData())
        compare_entry = self._get_selected_entry(self._compare_selector.currentData())
        if base_entry is None or compare_entry is None:
            self._diff_view.setPlainText("Select two rows to compare differences.")
            return
        if base_entry.index == compare_entry.index:
            self._diff_view.setPlainText("Select two different rows to see differences.")
            return
        page = self._page
        if page is None:
            self._diff_view.setPlainText("Preview data unavailable; unable to compute diff.")
            return
        columns = page.columns
        lines = [f"Comparing Row {base_entry.index + 1} vs Row {compare_entry.index + 1}"]
        for idx, column in enumerate(columns):
            left = base_entry.row[idx] if idx < len(base_entry.row) else None
            right = compare_entry.row[idx] if idx < len(compare_entry.row) else None
            if self._values_equal(left, right):
                marker = "="
                summary = self._stringify(left)
            else:
                marker = "→"
                summary = f"{self._stringify(left)} -> {self._stringify(right)}"
            lines.append(f" {column}: {marker} {summary}")
        self._diff_view.setPlainText("\n".join(lines))

    def _get_selected_entry(self, data: Optional[Union[int, object]]) -> Optional[_RowCacheEntry]:
        """Return the cached entry referenced by *data* (combo box payload)."""

        if data is None:
            return None
        try:
            idx = int(data)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
        for entry in self._rows:
            if entry.index == idx:
                return entry
        return None

    def _build_row_label(self, index: int, columns: Sequence[str], row: Sequence[object]) -> str:
        """Construct a human-readable label for a preview row."""

        parts: List[str] = []
        if self._table_info and self._table_info.primary_key:
            for key in self._table_info.primary_key:
                try:
                    col_index = columns.index(key)
                except ValueError:
                    continue
                parts.append(f"{key}={self._stringify(row[col_index])}")
        if not parts:
            for column, value in zip(columns, row):
                parts.append(f"{column}={self._stringify(value)}")
                if len(parts) == 2:
                    break
        label = ", ".join(parts) if parts else "(no columns)"
        return f"Row {index + 1}: {label}"

    @staticmethod
    def _stringify(value: object) -> str:
        """Return a short, single-line representation of *value*."""

        if value is None:
            return "NULL"
        text = str(value)
        text = text.replace("\n", " ").replace("\r", " ")
        if len(text) > 40:
            return f"{text[:37]}…"
        return text

    @staticmethod
    def _values_equal(left: object, right: object) -> bool:
        """Return True when *left* and *right* are considered equal."""

        if left is None and right is None:
            return True
        return left == right


# Compatibility alias mirroring other component exports
RowDiffViewerWidget = RowDiffViewer
