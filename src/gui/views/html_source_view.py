"""HTML Source Preview & Diff View (Milestone 5.5)

Presents two tabs:
 - Source: raw current HTML (read-only)
 - Diff: unified diff vs previous version (if any)

Lightweight syntax highlighting: only apply monospace + basic tag color via
stylesheet to avoid pulling larger deps.
"""

from __future__ import annotations
from typing import Optional
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QTabWidget,
    QPlainTextEdit,
)
from PyQt6.QtCore import Qt
from gui.services.html_diff import HtmlSource, HtmlDiffService


class HtmlSourceView(QWidget):
    """Widget encapsulating HTML source + diff display.

    Public API:
    - set_html_source(HtmlSource)
    """

    def __init__(self, diff_service: HtmlDiffService, parent: QWidget | None = None):
        super().__init__(parent)
        self._diff_service = diff_service
        self._source: Optional[HtmlSource] = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        self.title_label = QLabel("HTML Source")
        self.title_label.setStyleSheet("font-weight:600;font-size:14px")
        root.addWidget(self.title_label)
        self.tabs = QTabWidget()
        # Source tab
        self.txt_source = QPlainTextEdit()
        self.txt_source.setReadOnly(True)
        self.txt_source.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.txt_source.setStyleSheet(
            "font-family: Consolas, 'Courier New', monospace; font-size:12px"
        )
        self.tabs.addTab(self.txt_source, "Source")
        # Diff tab
        self.txt_diff = QPlainTextEdit()
        self.txt_diff.setReadOnly(True)
        self.txt_diff.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.txt_diff.setStyleSheet(
            "font-family: Consolas, 'Courier New', monospace; font-size:12px"
        )
        self.tabs.addTab(self.txt_diff, "Diff")
        root.addWidget(self.tabs)
        root.addStretch(1)

    # Data -----------------------------------------------------------
    def set_html_source(self, source: HtmlSource):
        self._source = source
        self.title_label.setText(f"HTML: {source.label}")
        self.txt_source.setPlainText(source.current_text or "")
        diff_text = self._diff_service.unified_diff(source.previous_text, source.current_text)
        self.txt_diff.setPlainText(diff_text or "(no previous version)")

    # Accessors for tests -------------------------------------------
    def has_diff(self) -> bool:  # pragma: no cover - trivial
        return bool(self.txt_diff.toPlainText().strip())


__all__ = ["HtmlSourceView"]
