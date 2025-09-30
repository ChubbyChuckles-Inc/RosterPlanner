"""Row detail inspector widget for the Database panel (Milestone 7.11.9).

Provides a compact UI surface that lets users explore individual rows
from the preview list, renders the row payload as JSON, and surfaces
related entities based on the table's foreign key definitions. The
widget is intentionally lightweight and keeps all logic synchronous since
inspector queries are limited to single-row lookups.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from typing import Optional, Sequence, Tuple, Union

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import (
    QComboBox,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

try:  # pragma: no cover - fallback for tests that skip theme mixin
    from gui.components.theme_aware import ThemeAwareMixin  # type: ignore
except Exception:  # pragma: no cover

    class ThemeAwareMixin:  # type: ignore[dead code]
        def apply_theme(self) -> None:  # noqa: D401 - no-op fallback
            pass


from gui.services.schema_introspection_service import ForeignKeyInfo, TableInfo
from gui.viewmodels.data_preview_model import (
    DataPreviewPage,
    DataPreviewRequest,
    LazyDataPreviewModel,
    PreviewCancelledError,
)

__all__ = ["RowDetailInspector"]


class RowDetailInspector(QWidget, ThemeAwareMixin):
    """Display JSON payload + FK previews for a selected row."""

    def __init__(
        self,
        preview_model: Optional[LazyDataPreviewModel],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("dbRowDetailInspector")
        self._preview_model = preview_model
        self._table: Optional[str] = None
        self._table_info: Optional[TableInfo] = None
        self._page: Optional[DataPreviewPage] = None
        self._building_selector = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = QLabel("Row detail inspector")
        header.setObjectName("dbRowInspectorHeader")
        layout.addWidget(header)

        self.row_selector = QComboBox()
        self.row_selector.setObjectName("dbRowSelector")
        self.row_selector.currentIndexChanged.connect(self._on_row_selected)  # type: ignore
        layout.addWidget(self.row_selector)

        self.json_view = QPlainTextEdit()
        self.json_view.setObjectName("dbRowJsonView")
        self.json_view.setReadOnly(True)
        self.json_view.setMinimumHeight(140)
        try:  # pragma: no cover - best effort (fonts may be unavailable in headless)
            self.json_view.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        except Exception:
            pass
        layout.addWidget(self.json_view)

        self.related_label = QLabel()
        self.related_label.setObjectName("dbRowRelatedLabel")
        self.related_label.setWordWrap(True)
        self.related_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self.related_label)

        if self._preview_model is None:
            self.show_unavailable("Row detail inspector requires preview service.")
        else:
            self.clear("Select a row from the preview list to inspect details.")

    # ------------------------------------------------------------------
    def set_context(self, table: str, table_info: Optional[TableInfo]) -> None:
        """Update the current table context for subsequent previews."""

        self._table = table
        self._table_info = table_info
        if table_info is None:
            self.show_unavailable("Row detail inspector unavailable (no schema info).")
        elif self._page:
            self.update_from_preview(self._page)

    def update_preview_model(self, model: Optional[LazyDataPreviewModel]) -> None:
        self._preview_model = model
        if model is None:
            self.show_unavailable("Row detail inspector requires preview service.")
        elif not self._page:
            self.clear("Select a row from the preview list to inspect details.")

    def update_from_preview(self, page: Optional[DataPreviewPage]) -> None:
        """Refresh selector + detail views based on preview page data."""

        if self._preview_model is None:
            self.show_unavailable("Row detail inspector requires preview service.")
            return
        self._page = page
        if page is None or not page.rows:
            self.clear("No rows available to inspect. Adjust filters or ingest data.")
            return
        self._building_selector = True
        try:
            self.row_selector.clear()
            for idx, row in enumerate(page.rows):
                label = self._build_row_label(idx, page.columns, row)
                self.row_selector.addItem(label, idx)
            self.row_selector.setEnabled(True)
        finally:
            self._building_selector = False
        self.row_selector.setCurrentIndex(0)
        self._display_row(0)

    def clear(self, message: str = "") -> None:
        """Reset inspector state while keeping current context."""

        self.row_selector.blockSignals(True)
        self.row_selector.clear()
        self.row_selector.setEnabled(False)
        self.row_selector.blockSignals(False)
        self.json_view.setPlainText(message)
        self.related_label.setText("")

    def show_unavailable(self, message: str) -> None:
        self.clear(message)
        self._page = None

    # ------------------------------------------------------------------
    def _on_row_selected(self, index: int) -> None:
        if self._building_selector:
            return
        self._display_row(index)

    def _display_row(self, index: int) -> None:
        if self._page is None or index < 0 or index >= len(self._page.rows):
            return
        row_tuple = self._page.rows[index]
        columns = self._page.columns
        row_dict = OrderedDict((col, row_tuple[i]) for i, col in enumerate(columns))
        self.json_view.setPlainText(self._format_json(row_dict))
        self._populate_related(row_dict)

    def _populate_related(self, row: OrderedDict[str, object]) -> None:
        if not self._table_info or not self._table_info.foreign_keys:
            self.related_label.setText("No foreign key relationships for this table.")
            return
        if self._preview_model is None:
            self.related_label.setText("Related previews unavailable (preview service missing).")
            return
        lines = []
        for fk in self._table_info.foreign_keys:
            header = f"<b>{fk.column}</b> → {fk.ref_table}.{fk.ref_column}"
            value = row.get(fk.column)
            if value is None:
                lines.append(f"{header}: <i>NULL</i>")
                continue
            preview = self._fetch_related_preview(fk, value)
            if preview is None:
                lines.append(
                    f"{header} = <code>{self._stringify(value)}</code><br/>&nbsp;&nbsp;<i>No matching row.</i>"
                )
            elif isinstance(preview, str):
                lines.append(
                    f"{header} = <code>{self._stringify(value)}</code><br/>&nbsp;&nbsp;<i>{preview}</i>"
                )
            else:
                columns, row_tuple = preview
                summary = self._build_related_summary(columns, row_tuple)
                lines.append(
                    f"{header} = <code>{self._stringify(value)}</code><br/>&nbsp;&nbsp;{summary}"
                )
        if not lines:
            self.related_label.setText("No related entities could be resolved.")
        else:
            self.related_label.setText("<br/>".join(lines))

    def _fetch_related_preview(
        self, fk: ForeignKeyInfo, value: object
    ) -> Optional[Union[Tuple[Tuple[str, ...], Tuple[object, ...]], str]]:
        if self._preview_model is None:
            return "Preview service unavailable"
        where_clause = f"{self._quote_ident(fk.ref_column)} = ?"
        request = DataPreviewRequest(
            table=fk.ref_table,
            limit=1,
            where=where_clause,
            parameters=(value,),
        )
        try:
            page = self._preview_model.fetch_page(request, timeout=1.5)
        except PreviewCancelledError:
            return "Lookup cancelled"
        except Exception as exc:  # pragma: no cover - defensive (rare)
            return f"Lookup failed: {exc.__class__.__name__}"
        if not page.rows:
            return None
        return page.columns, page.rows[0]

    # ------------------------------------------------------------------
    def _build_row_label(
        self, index: int, columns: Tuple[str, ...], row: Tuple[object, ...]
    ) -> str:
        parts = []
        if self._table_info and self._table_info.primary_key:
            for key in self._table_info.primary_key:
                try:
                    idx = columns.index(key)
                except ValueError:
                    continue
                parts.append(f"{key}={self._stringify(row[idx])}")
        if not parts:
            for col, value in zip(columns, row):
                parts.append(f"{col}={self._stringify(value)}")
                if len(parts) == 2:
                    break
        joined = ", ".join(parts) if parts else "(no columns)"
        return f"Row {index + 1}: {joined}"

    @staticmethod
    def _format_json(row: OrderedDict[str, object]) -> str:
        try:
            return json.dumps(row, indent=2, default=RowDetailInspector._json_default)
        except Exception:
            safe_row = {key: RowDetailInspector._safe_string(value) for key, value in row.items()}
            return json.dumps(safe_row, indent=2)

    @staticmethod
    def _json_default(value: object) -> str:
        return RowDetailInspector._safe_string(value)

    @staticmethod
    def _safe_string(value: object) -> str:
        if value is None:
            return "null"
        text = str(value)
        if len(text) > 1000:
            text = text[:997] + "…"
        return text

    @staticmethod
    def _build_related_summary(columns: Sequence[str], row: Sequence[object]) -> str:
        parts: list[str] = []
        for col, value in zip(columns, row):
            if value is None:
                continue
            parts.append(f"{col}={RowDetailInspector._stringify(value)}")
            if len(parts) == 3:
                break
        if not parts:
            return "Preview: (no non-null columns)"
        return "Preview: " + ", ".join(parts)

    @staticmethod
    def _stringify(value: object) -> str:
        if value is None:
            return "NULL"
        text = str(value)
        text = text.replace("\n", " ").replace("\r", " ")
        if len(text) > 32:
            return text[:29] + "…"
        return text

    @staticmethod
    def _quote_ident(value: str) -> str:
        escaped = value.replace('"', '""')
        return f'"{escaped}"'


# Compatibility alias for potential future usage
RowDetailInspectorWidget = RowDetailInspector
