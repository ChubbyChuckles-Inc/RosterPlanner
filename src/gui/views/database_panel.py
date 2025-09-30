"""Database Panel Scaffold (Milestone 7.11.1).

Initial dockable widget giving a read-only overview:
 - Left: table list
 - Right: column details placeholder + relationship graph
 - Safety banner (read-only mode) and admin toggle persisted via database safety service
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QListWidget,
    QLabel,
    QSplitter,
    QListWidgetItem,
    QHBoxLayout,
    QCheckBox,
    QLineEdit,
)
from PyQt6.QtCore import Qt, QTimer

try:  # pragma: no cover
    from gui.components.theme_aware import ThemeAwareMixin  # type: ignore
except Exception:  # pragma: no cover

    class ThemeAwareMixin:  # type: ignore
        def apply_theme(self):  # noqa: D401
            pass


from gui.components.schema_graph_widget import SchemaGraphWidget
from gui.components.row_detail_inspector import RowDetailInspector
from gui.components.row_diff_viewer import RowDiffViewer
from gui.components.query_runner import QueryRunnerWidget
from gui.services.data_freshness_service import humanize_age
from gui.services.service_locator import services as _services  # type: ignore
from gui.viewmodels.data_preview_model import (
    DataPreviewRequest,
    LazyDataPreviewModel,
    PreviewCancelledError,
)
from gui.services.schema_introspection_service import TableInfo


class DatabasePanel(QWidget, ThemeAwareMixin):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("databasePanel")
        self._safety_service = _services.try_get("database_safety_service")
        self._data_preview_model: Optional[LazyDataPreviewModel] = _services.try_get(
            "data_preview_model"
        )
        self._schema_service = _services.try_get("schema_introspection_service")
        self._sqlite_conn = _services.try_get("sqlite_conn")
        self._preview_limit = 5
        self._active_table: Optional[str] = None
        initial_admin = False
        if self._safety_service is not None:
            try:
                initial_admin = bool(self._safety_service.admin_enabled())
            except Exception:
                initial_admin = False
        self._admin_enabled = initial_admin
        self._build_ui()
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(250)
        self._filter_timer.timeout.connect(self._refresh_details_for_current_table)
        if self._data_preview_model is None:
            self.quick_filter_input.setEnabled(False)
            self.quick_filter_input.setPlaceholderText(
                "Quick filter unavailable (preview service missing)"
            )
        self._populate_tables()
        self._apply_admin_state()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(6)
        header = QLabel("Database Overview")
        header.setObjectName("viewTitleLabel")
        header_row.addWidget(header)
        header_row.addStretch(1)
        self.admin_toggle = QCheckBox("Enable Admin Mode")
        self.admin_toggle.setObjectName("dbAdminToggle")
        self.admin_toggle.setChecked(self._admin_enabled)
        if self._safety_service is None:
            self.admin_toggle.setEnabled(False)
            self.admin_toggle.setToolTip("Safety service unavailable; admin mode disabled.")
        header_row.addWidget(self.admin_toggle)
        root.addLayout(header_row)

        split = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(split, 1)

        self.table_list = QListWidget()
        self.table_list.setObjectName("dbTableList")
        self.table_list.setSortingEnabled(True)
        split.addWidget(self.table_list)

        detail_container = QWidget()
        detail_layout = QVBoxLayout(detail_container)
        detail_layout.setContentsMargins(6, 0, 0, 0)
        detail_layout.setSpacing(6)

        self.detail_label = QLabel(
            "Select a table to inspect. Future tasks will add sample rows, indexes, graph views."
        )
        self.detail_label.setWordWrap(True)
        self.detail_label.setObjectName("dbDetailPlaceholder")
        detail_layout.addWidget(self.detail_label)

        self.quick_filter_input = QLineEdit()
        self.quick_filter_input.setObjectName("dbQuickFilterInput")
        self.quick_filter_input.setPlaceholderText("Quick filter (substring match across columns)")
        detail_layout.addWidget(self.quick_filter_input)

        self.row_inspector = RowDetailInspector(self._data_preview_model, detail_container)
        detail_layout.addWidget(self.row_inspector)

        self.row_diff_viewer = RowDiffViewer(detail_container)
        detail_layout.addWidget(self.row_diff_viewer)
        if self._data_preview_model is None:
            self.row_diff_viewer.show_unavailable("Row diff viewer requires preview service.")

        self.query_runner = QueryRunnerWidget(detail_container)
        self.query_runner.set_connection(self._sqlite_conn)
        detail_layout.addWidget(self.query_runner)

        self.graph_widget = SchemaGraphWidget(detail_container)
        detail_layout.addWidget(self.graph_widget, 1)

        split.addWidget(detail_container)
        split.setStretchFactor(1, 1)

        self.banner = QLabel("Safety Mode: READ-ONLY")
        self.banner.setObjectName("dbSafetyBanner")
        root.addWidget(self.banner)

        self.admin_notice = QLabel(
            "Admin actions are hidden in read-only mode. Enable admin mode to perform maintenance operations."
        )
        self.admin_notice.setWordWrap(True)
        self.admin_notice.setObjectName("dbAdminNotice")
        root.addWidget(self.admin_notice)

        self.admin_actions = QWidget()
        self.admin_actions.setObjectName("dbAdminActions")
        admin_layout = QVBoxLayout(self.admin_actions)
        admin_layout.setContentsMargins(0, 0, 0, 0)
        admin_layout.setSpacing(4)
        placeholder = QLabel(
            "Admin-only maintenance actions will appear here in future milestones."
        )
        placeholder.setWordWrap(True)
        placeholder.setObjectName("dbAdminPlaceholder")
        admin_layout.addWidget(placeholder)
        root.addWidget(self.admin_actions)

        self.table_list.currentItemChanged.connect(self._on_table_selected)  # type: ignore
        self.admin_toggle.stateChanged.connect(self._on_admin_toggled)  # type: ignore
        self.quick_filter_input.textChanged.connect(self._on_quick_filter_changed)  # type: ignore

    def _populate_tables(self) -> None:
        svc = _services.try_get("schema_introspection_service")  # type: ignore
        self._schema_service = svc
        if not svc:
            return
        try:
            names = svc.list_tables()
        except Exception:  # pragma: no cover
            names = []
        self.table_list.clear()
        for name in names:
            QListWidgetItem(name, self.table_list)

    def _on_table_selected(self, current, _previous):  # pragma: no cover - UI reaction
        if not current:
            self._active_table = None
            self.detail_label.setText(
                "Select a table to inspect. Future tasks will add sample rows, indexes, graph views."
            )
            self.graph_widget.clear()
            self.row_inspector.clear("Select a table to inspect rows.")
            self.row_diff_viewer.clear("Select a table to compare rows.")
            self.query_runner.set_default_table(None)
            return
        self._active_table = current.text()
        self._filter_timer.stop()
        self._refresh_details_for_current_table()

    def apply_theme(self):  # pragma: no cover - styling hook placeholder
        pass

    # ------------------------------------------------------------------
    def is_admin_mode(self) -> bool:
        return self._admin_enabled

    def _refresh_details_for_current_table(self) -> None:
        name = self._active_table
        if not name:
            return
        svc = self._get_schema_service()
        if not svc:
            self.detail_label.setText(f"{name}\n(No introspection service)")
            self.graph_widget.clear()
            self.row_inspector.show_unavailable(
                "Row detail inspector unavailable (no schema info)."
            )
            self.row_diff_viewer.show_unavailable("Row diff viewer unavailable (no schema info).")
            self.query_runner.set_default_table(None)
            return
        ti = svc.get_table_info(name)
        if not ti:
            self.detail_label.setText(f"{name}\n(No column info)")
            self.graph_widget.clear()
            self.row_inspector.show_unavailable(
                "Row detail inspector unavailable (no schema info)."
            )
            self.row_diff_viewer.show_unavailable("Row diff viewer unavailable (no schema info).")
            self.query_runner.set_default_table(None)
            return
        self.row_inspector.set_context(name, ti)
        self.row_diff_viewer.set_context(name, ti)
        self.query_runner.set_default_table(name)
        stats_map: Dict[str, object] = {}
        if hasattr(svc, "get_column_stats"):
            try:
                stats_map = svc.get_column_stats(name)
            except Exception:
                stats_map = {}
        lines = self._build_table_summary_lines(ti, stats_map)
        lines.extend(self._build_preview_lines(name))
        self.detail_label.setText("\n".join(lines))
        self.graph_widget.set_focus_table(name)

    def _build_table_summary_lines(self, ti: TableInfo, stats_map: Dict[str, object]) -> list[str]:
        lines: list[str] = [f"Table: {ti.name}"]
        lines.append("Table Profile:")
        lines.append(f" • Rows: {self._format_row_count(ti.row_count)}")
        lines.append(f" • Size: {self._format_size(ti.approx_page_count, ti.approx_size_bytes)}")
        lines.append(f" • Last ingest: {self._format_last_ingest(ti.last_ingested_at)}")
        lines.append("")
        lines.append("Columns:")
        for col in ti.columns:
            markers = []
            if col.is_primary_key:
                markers.append("PK")
            if col.not_null:
                markers.append("NOT NULL")
            default = f" DEFAULT={col.default}" if col.default is not None else ""
            marker_text = f" [{', '.join(markers)}]" if markers else ""
            type_text = col.type or "TEXT"
            lines.append(f" • {col.name}: {type_text}{marker_text}{default}")
            stats = stats_map.get(col.name)
            stats_line = self._format_column_stats(stats)
            if stats_line:
                lines.append(f"    ↳ Stats: {stats_line}")

        if ti.foreign_keys:
            lines.append("")
            lines.append("Foreign Keys:")
            for fk in ti.foreign_keys:
                lines.append(
                    f" • {fk.column} → {fk.ref_table}.{fk.ref_column} "
                    f"(ON UPDATE {fk.on_update}, ON DELETE {fk.on_delete})"
                )

        if ti.indexes:
            lines.append("")
            lines.append("Indexes:")
            for idx in ti.indexes:
                cols = ", ".join(idx.columns)
                unique = " UNIQUE" if idx.unique else ""
                lines.append(f" • {idx.name}:{unique} ({cols})")
        return lines

    def _build_preview_lines(self, table: str) -> list[str]:
        model = self._data_preview_model
        if model is None:
            self.row_inspector.show_unavailable("Row detail inspector requires preview service.")
            self.row_diff_viewer.show_unavailable("Row diff viewer requires preview service.")
            return []
        quick_text = self.quick_filter_input.text().strip()
        request = DataPreviewRequest(
            table=table, limit=self._preview_limit, quick_filter=quick_text
        )
        try:
            page = model.fetch_page(request, timeout=2.0)
        except PreviewCancelledError:
            self.row_diff_viewer.clear("Preview cancelled; no diff available.")
            return ["", "Preview rows: cancelled"]
        except Exception:
            self.row_diff_viewer.clear("Preview rows unavailable (query failed).")
            return ["", "Preview rows unavailable (query failed)"]
        self.row_inspector.update_from_preview(page)
        self.row_diff_viewer.update_from_preview(page)
        heading = "Preview rows"
        if quick_text:
            heading += f" (filter: {quick_text})"
        lines = ["", f"{heading}:"]
        if not page.rows:
            lines.append(" • No rows match current filter")
            self.row_diff_viewer.clear("No rows available to diff. Adjust filters or ingest data.")
            return lines
        columns = " | ".join(page.columns) if page.columns else "(no columns)"
        lines.append(f" • {columns}")
        for row in page.rows:
            formatted = " | ".join(self._format_preview_value(value) for value in row)
            lines.append(f"   {formatted}")
        if page.truncated:
            lines.append("   …")
        return lines

    def _on_quick_filter_changed(self, _text: str) -> None:
        if self._data_preview_model is None:
            return
        self._filter_timer.stop()
        self._filter_timer.start()

    def _get_schema_service(self):
        svc = _services.try_get("schema_introspection_service")
        self._schema_service = svc
        return svc

    @staticmethod
    def _format_preview_value(value: object) -> str:
        if value is None:
            return "NULL"
        text = str(value)
        text = text.replace("\n", " ").replace("\r", " ")
        if len(text) > 40:
            return f"{text[:37]}…"
        return text

    def _on_admin_toggled(self, state: int) -> None:
        enabled = state == Qt.CheckState.Checked.value
        if self._safety_service is not None:
            try:
                changed = self._safety_service.set_admin_enabled(enabled)
                self._admin_enabled = bool(self._safety_service.admin_enabled())
                if not changed and self._admin_enabled != enabled:
                    # Re-sync checkbox without re-triggering signal
                    self.admin_toggle.blockSignals(True)
                    self.admin_toggle.setChecked(self._admin_enabled)
                    self.admin_toggle.blockSignals(False)
            except Exception:
                self._admin_enabled = False
                self.admin_toggle.blockSignals(True)
                self.admin_toggle.setChecked(False)
                self.admin_toggle.blockSignals(False)
        else:
            self._admin_enabled = enabled
        self._apply_admin_state()

    def _apply_admin_state(self) -> None:
        if getattr(self, "admin_toggle", None) is None:
            return
        if self.admin_toggle.isChecked() != self._admin_enabled:
            self.admin_toggle.blockSignals(True)
            self.admin_toggle.setChecked(self._admin_enabled)
            self.admin_toggle.blockSignals(False)
        if self._admin_enabled:
            self.banner.setText("Safety Mode: ADMIN (use with caution)")
            self.admin_actions.show()
            self.admin_notice.hide()
            self.setProperty("dbAdminMode", "admin")
        else:
            self.banner.setText("Safety Mode: READ-ONLY")
            self.admin_actions.hide()
            self.admin_notice.show()
            self.setProperty("dbAdminMode", "readonly")
        try:
            self.style().unpolish(self)
            self.style().polish(self)
        except Exception:  # pragma: no cover
            pass

    # ------------------------------------------------------------------
    @staticmethod
    def _format_row_count(value: Optional[int]) -> str:
        if value is None:
            return "n/a"
        return f"{value:,}"

    def _format_size(self, pages: Optional[int], byte_count: Optional[int]) -> str:
        segments: list[str] = []
        if pages is not None:
            segments.append(f"{pages:,} pages")
        if byte_count is not None:
            segments.append(f"~{self._human_readable_bytes(byte_count)}")
        if not segments:
            return "n/a"
        return ", ".join(segments)

    def _format_last_ingest(self, raw: Optional[str]) -> str:
        if not raw:
            return "n/a"
        parsed = self._parse_timestamp(raw)
        if not parsed:
            return raw
        age = max(0, int((datetime.utcnow() - parsed).total_seconds()))
        friendly_age = humanize_age(age)
        return f"{parsed.strftime('%Y-%m-%d %H:%M:%S')} ({friendly_age})"

    @staticmethod
    def _format_column_stats(stats) -> Optional[str]:
        if not stats:
            return None
        parts: list[str] = []
        if stats.distinct_count is not None:
            parts.append(f"distinct≈{stats.distinct_count}")
        if stats.null_fraction is not None:
            parts.append(f"null≈{stats.null_fraction:.1f}%")
        if stats.min_value is not None or stats.max_value is not None:
            range_part = " ↔ ".join(
                [value for value in (stats.min_value, stats.max_value) if value is not None]
            )
            if range_part:
                parts.append(f"range: {range_part}")
        if stats.sample_rows:
            parts.append(f"n={stats.sample_rows}")
        return ", ".join(parts) if parts else None

    @staticmethod
    def _parse_timestamp(raw: str) -> Optional[datetime]:
        text = raw.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1]
        for parser in (datetime.fromisoformat,):
            try:
                return parser(text)
            except Exception:
                continue
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
            try:
                return datetime.strptime(text, fmt)
            except Exception:
                continue
        return None

    @staticmethod
    def _human_readable_bytes(byte_count: int) -> str:
        thresholds = ["bytes", "KB", "MB", "GB", "TB"]
        size = float(byte_count)
        for unit in thresholds:
            if size < 1024 or unit == thresholds[-1]:
                if unit == "bytes":
                    return f"{int(size)} bytes"
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{byte_count} bytes"
