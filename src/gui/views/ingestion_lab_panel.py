"""Ingestion Lab Panel (Milestone 7.10.1).

Provides a dockable multi-pane workspace for interactive ingestion rule
experimentation. This initial implementation delivers the structural UI:
 - File Navigator: lists available HTML assets under the configured data dir
 - Rule Editor: editable JSON/YAML text (currently plain text with validation stub)
 - Preview: shows a snippet or meta-info for a selected file
 - Execution Log: append-only log area for future sandbox run output

Subsequent milestones (7.10.6+) will extend rule schema parsing, diff
visualization, sandbox DB application, assertions, etc.

Design Goals:
 - Maintainable: clear separation of concerns, small helper methods
 - Testable: expose accessors for key widgets & provide deterministic refresh
 - Non-blocking: file discovery performed synchronously (fast for typical dataset)
 - Extensible: future injection of rule evaluators via service locator

Usage:
    panel = IngestionLabPanel(base_dir="data")
    panel.refresh_file_list()

"""

from __future__ import annotations
from typing import List, Optional
import os
import glob

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QSplitter,
    QPushButton,
    QLabel,
    QTextEdit,
    QSizePolicy,
)
from PyQt6.QtCore import Qt

__all__ = ["IngestionLabPanel"]

HTML_EXTENSIONS = {".html", ".htm"}


class IngestionLabPanel(QWidget):
    """Dockable panel container for the Ingestion Lab.

    Parameters
    ----------
    base_dir: str
        Root data directory containing scraped HTML assets (typically `data/`).
    """

    def __init__(self, base_dir: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("ingestionLabPanel")
        self._base_dir = base_dir
        self._build_ui()
        self.refresh_file_list()

    # ------------------------------------------------------------------
    # UI Construction
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        # Top action bar
        actions = QHBoxLayout()
        self.btn_refresh = QPushButton("Refresh")
        self.btn_preview = QPushButton("Preview")
        self.btn_preview.setEnabled(False)
        actions.addWidget(self.btn_refresh)
        actions.addWidget(self.btn_preview)
        actions.addStretch(1)
        root.addLayout(actions)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        root.addWidget(splitter, 1)

        # Left: File Navigator
        self.file_list = QListWidget()
        self.file_list.setObjectName("ingestionLabFileList")
        self.file_list.itemSelectionChanged.connect(self._on_file_selection_changed)  # type: ignore
        splitter.addWidget(self.file_list)

        # Middle: Rule Editor & Preview stacked vertically
        mid_split = QSplitter(Qt.Orientation.Vertical, self)
        splitter.addWidget(mid_split)

        self.rule_editor = QPlainTextEdit()
        self.rule_editor.setObjectName("ingestionLabRuleEditor")
        self.rule_editor.setPlaceholderText(
            "# Define extraction rules here (YAML or JSON)\n# e.g.\n# ranking_table:\n#   selector: 'table.ranking'\n#   columns: [team, points, diff]\n"
        )
        mid_split.addWidget(self.rule_editor)

        self.preview_area = QTextEdit()
        self.preview_area.setObjectName("ingestionLabPreview")
        self.preview_area.setReadOnly(True)
        self.preview_area.setPlaceholderText("Select a file then click Preview to see metadata.")
        mid_split.addWidget(self.preview_area)

        # Right: Execution Log
        self.log_area = QPlainTextEdit()
        self.log_area.setObjectName("ingestionLabLog")
        self.log_area.setReadOnly(True)
        self.log_area.setPlaceholderText(
            "Execution log will appear here (rule validation, parse results)."
        )
        splitter.addWidget(self.log_area)

        splitter.setStretchFactor(0, 25)
        splitter.setStretchFactor(1, 45)
        splitter.setStretchFactor(2, 30)

        # Connections
        self.btn_refresh.clicked.connect(self.refresh_file_list)  # type: ignore
        self.btn_preview.clicked.connect(self._on_preview_clicked)  # type: ignore

    # ------------------------------------------------------------------
    # File Discovery
    def refresh_file_list(self) -> None:
        """Scan the base directory recursively for HTML assets and populate the list."""
        self.file_list.clear()
        data_root = self._base_dir
        if not os.path.isdir(data_root):  # pragma: no cover - defensive
            return
        pattern = os.path.join(data_root, "**", "*.html")
        files = sorted(glob.glob(pattern, recursive=True))
        for fpath in files:
            rel = os.path.relpath(fpath, data_root)
            item = QListWidgetItem(rel)
            item.setData(Qt.ItemDataRole.UserRole, fpath)
            self.file_list.addItem(item)
        self._append_log(f"Refreshed: {len(files)} HTML files found.")

    # ------------------------------------------------------------------
    # Events & Actions
    def _on_file_selection_changed(self) -> None:
        has_sel = len(self.file_list.selectedItems()) > 0
        self.btn_preview.setEnabled(has_sel)

    def _on_preview_clicked(self) -> None:
        items = self.file_list.selectedItems()
        if not items:
            return
        target = items[0]
        fpath = target.data(Qt.ItemDataRole.UserRole)
        try:
            stat = os.stat(fpath)
            with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                snippet = fh.read(800)
            meta = [
                f"File: {fpath}",
                f"Size: {stat.st_size} bytes",
                f"Modified: {int(stat.st_mtime)} (epoch)",
                "--- Snippet ---",
                snippet,
            ]
            self.preview_area.setPlainText("\n".join(meta))
            self._append_log(f"Previewed: {target.text()}")
        except Exception as e:  # pragma: no cover - unlikely
            self.preview_area.setPlainText(f"Error reading file: {e}")
            self._append_log(f"ERROR preview {target.text()}: {e}")

    # ------------------------------------------------------------------
    # Logging helper
    def _append_log(self, line: str) -> None:
        self.log_area.appendPlainText(line)

    # ------------------------------------------------------------------
    # Accessors used in tests
    def listed_files(self) -> List[str]:
        return [self.file_list.item(i).text() for i in range(self.file_list.count())]

    def base_dir(self) -> str:
        return self._base_dir
