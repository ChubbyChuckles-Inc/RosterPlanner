"""Database Panel Scaffold (Milestone 7.11.1).

Initial dockable widget giving a read-only overview:
 - Left: table list
 - Right: column details placeholder
 - Safety banner (read-only mode)
"""

from __future__ import annotations

from typing import Optional
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QListWidget,
    QLabel,
    QSplitter,
    QListWidgetItem,
)
from PyQt6.QtCore import Qt

try:  # pragma: no cover
    from gui.components.theme_aware import ThemeAwareMixin  # type: ignore
except Exception:  # pragma: no cover

    class ThemeAwareMixin:  # type: ignore
        def apply_theme(self):  # noqa: D401
            pass


from gui.components.schema_graph_widget import SchemaGraphWidget
from gui.services.service_locator import services as _services  # type: ignore


class DatabasePanel(QWidget, ThemeAwareMixin):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("databasePanel")
        self._build_ui()
        self._populate_tables()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        header = QLabel("Database Overview (Read-Only Mode)")
        header.setObjectName("viewTitleLabel")
        root.addWidget(header)

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

        self.graph_widget = SchemaGraphWidget(detail_container)
        detail_layout.addWidget(self.graph_widget, 1)

        split.addWidget(detail_container)
        split.setStretchFactor(1, 1)

        banner = QLabel("Safety Mode: READ-ONLY")
        banner.setObjectName("dbSafetyBanner")
        root.addWidget(banner)

        self.table_list.currentItemChanged.connect(self._on_table_selected)  # type: ignore

    def _populate_tables(self) -> None:
        svc = _services.try_get("schema_introspection_service")  # type: ignore
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
            self.detail_label.setText(
                "Select a table to inspect. Future tasks will add sample rows, indexes, graph views."
            )
            self.graph_widget.clear()
            return
        name = current.text()
        svc = _services.try_get("schema_introspection_service")
        if not svc:
            self.detail_label.setText(f"{name}\n(No introspection service)")
            self.graph_widget.clear()
            return
        ti = svc.get_table_info(name)
        if not ti:
            self.detail_label.setText(f"{name}\n(No column info)")
            self.graph_widget.clear()
            return
        lines = [f"Table: {ti.name}"]
        if ti.row_count is not None:
            lines.append(f"Rows (cached): {ti.row_count}")

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

        self.detail_label.setText("\n".join(lines))
        self.graph_widget.set_focus_table(name)

    def apply_theme(self):  # pragma: no cover - styling hook placeholder
        pass
