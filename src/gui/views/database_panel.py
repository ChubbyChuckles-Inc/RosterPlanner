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

        self.detail_placeholder = QLabel(
            "Select a table to inspect. Future tasks will add sample rows, indexes, graph views."
        )
        self.detail_placeholder.setWordWrap(True)
        self.detail_placeholder.setObjectName("dbDetailPlaceholder")
        split.addWidget(self.detail_placeholder)
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
            self.detail_placeholder.setText(
                "Select a table to inspect. Future tasks will add sample rows, indexes, graph views."
            )
            return
        name = current.text()
        svc = _services.try_get("schema_introspection_service")
        if not svc:
            self.detail_placeholder.setText(f"{name}\n(No introspection service)")
            return
        ti = svc.get_table_info(name)
        if not ti:
            self.detail_placeholder.setText(f"{name}\n(No column info)")
            return
        lines = [f"Table: {ti.name}"]
        for c in ti.columns:
            nn = " NOT NULL" if c.not_null else ""
            pk = " PK" if c.pk else ""
            default = f" DEFAULT={c.default}" if c.default is not None else ""
            lines.append(f" - {c.name} ({c.type}){nn}{pk}{default}")
        self.detail_placeholder.setText("\n".join(lines))

    def apply_theme(self):  # pragma: no cover - styling hook placeholder
        pass
