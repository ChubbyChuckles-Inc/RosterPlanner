"""Graph mini-view widget for schema relationships (Milestone 7.11.4)."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel, QPlainTextEdit, QStackedWidget, QVBoxLayout, QWidget

from gui.services.service_locator import services
from gui.viewmodels.schema_graph_viewmodel import SchemaGraphViewModel

try:  # pragma: no cover - optional dependency
    import graphviz  # type: ignore

    _GRAPHVIZ_AVAILABLE = True
except Exception:  # pragma: no cover
    graphviz = None  # type: ignore
    _GRAPHVIZ_AVAILABLE = False


class SchemaGraphWidget(QWidget):
    """Displays a relationship graph using Graphviz with textual fallback."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        viewmodel: Optional[SchemaGraphViewModel] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("schemaGraphWidget")
        self._viewmodel = viewmodel or self._auto_viewmodel()
        self._graphviz_enabled = _GRAPHVIZ_AVAILABLE
        self._current_focus: Optional[str] = None

        self._stack = QStackedWidget(self)
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setObjectName("schemaGraphImage")
        self._text_fallback = QPlainTextEdit()
        self._text_fallback.setReadOnly(True)
        self._text_fallback.setObjectName("schemaGraphAscii")
        self._stack.addWidget(self._image_label)
        self._stack.addWidget(self._text_fallback)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack)

        self._show_placeholder()

    # ------------------------------------------------------------------
    def set_focus_table(self, table: Optional[str]) -> None:
        self._current_focus = table
        if self._viewmodel is None:
            self._show_text("Schema graph unavailable (no introspection service)")
            return
        graph = self._viewmodel.build_graph(table)
        if not graph.nodes:
            self._show_text("No tables detected")
            return
        dot = self._viewmodel.render_dot(graph)
        if self._graphviz_enabled and self._render_graphviz(dot):
            return
        ascii_text = self._viewmodel.render_ascii(graph)
        self._show_text(ascii_text)

    def clear(self) -> None:
        self._current_focus = None
        self._show_placeholder()

    # ------------------------------------------------------------------
    def _show_placeholder(self) -> None:
        self._show_text("Select a table to view relationship graph")

    def _show_text(self, text: str) -> None:
        self._text_fallback.setPlainText(text)
        self._stack.setCurrentWidget(self._text_fallback)

    def _render_graphviz(self, dot_source: str) -> bool:
        if not self._graphviz_enabled or graphviz is None:
            return False
        try:  # pragma: no cover - depends on optional binary
            graph = graphviz.Source(dot_source)
            binary = graph.pipe(format="png")
        except Exception:
            self._graphviz_enabled = False
            return False
        pixmap = QPixmap()
        if not pixmap.loadFromData(binary):
            self._graphviz_enabled = False
            return False
        self._image_label.setPixmap(pixmap)
        self._stack.setCurrentWidget(self._image_label)
        return True

    def _auto_viewmodel(self) -> Optional[SchemaGraphViewModel]:
        introspection = services.try_get("schema_introspection_service")  # type: ignore[arg-type]
        if introspection is None:
            return None
        return SchemaGraphViewModel(introspection)
