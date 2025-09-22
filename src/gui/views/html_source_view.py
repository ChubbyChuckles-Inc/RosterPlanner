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
    QCheckBox,
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
        # Toggle row
        self.chk_clean = QCheckBox("Show cleaned HTML")
        self.chk_clean.stateChanged.connect(self._on_toggle_mode)  # type: ignore
        root.addWidget(self.chk_clean)
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
        self._apply_mode()

    # Mode handling -------------------------------------------------
    def _apply_mode(self):
        if not self._source:
            return
        raw_cur = self._source.current_text or ""
        raw_prev = self._source.previous_text
        if self.chk_clean.isChecked():
            cur = self._diff_service.clean_html(raw_cur)
            prev = self._diff_service.clean_html(raw_prev) if raw_prev else None
        else:
            cur = raw_cur
            prev = raw_prev
        self.txt_source.setPlainText(cur)
        diff_text = self._diff_service.unified_diff(prev, cur)
        if not diff_text.strip():
            diff_text = "(no previous version)" if not prev else "(no differences)"
        self.txt_diff.setPlainText(diff_text)

    def _on_toggle_mode(self):  # pragma: no cover - GUI path
        self._apply_mode()

    # Accessors for tests -------------------------------------------
    def has_diff(self) -> bool:  # pragma: no cover - trivial
        return bool(self.txt_diff.toPlainText().strip())

    # Export integration (Milestone 5.6) ---------------------------------
    def get_export_rows(self):  # pragma: no cover - simple
        # Provide tabular export with two columns: type, content lines
        headers = ["Section", "Content"]
        rows = [["source", self.txt_source.toPlainText()]]
        diff_text = self.txt_diff.toPlainText()
        rows.append(["diff", diff_text])
        return headers, rows

    def get_export_payload(self):  # pragma: no cover - simple
        return {
            "label": self.title_label.text(),
            "source": self.txt_source.toPlainText(),
            "diff": self.txt_diff.toPlainText(),
        }


__all__ = ["HtmlSourceView"]
