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
    QListWidget,  # legacy (will alias to new tree for backward compat with early tests)
    QListWidgetItem,  # retained for minimal diff; not used after grouping refactor
    QPlainTextEdit,
    QSplitter,
    QPushButton,
    QLabel,
    QTextEdit,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
)
from PyQt6.QtCore import Qt

__all__ = ["IngestionLabPanel"]

HTML_EXTENSIONS = {".html", ".htm"}

# Phase grouping heuristics (Milestone 7.10.2). Each entry is (phase_id, display_label, predicate)
# The predicate receives (relative_path, filename_lower) and returns True if the file belongs.
PHASE_PATTERNS = [
    ("ranking_tables", "Ranking Tables", lambda rel, fn: fn.startswith("ranking_table_")),
    ("team_rosters", "Team Rosters", lambda rel, fn: fn.startswith("team_roster_")),
    ("club_overviews", "Club Overviews", lambda rel, fn: "club" in fn and "overview" in fn),
    ("player_histories", "Player Histories", lambda rel, fn: "history" in fn or "tracking" in fn),
]
OTHER_PHASE_ID = "other"


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

        # Left: File Navigator (grouped). Replace flat list with tree (phase -> files)
        self.file_tree = QTreeWidget()
        self.file_tree.setObjectName("ingestionLabFileTree")
        self.file_tree.setHeaderLabels(["Phase", "File", "Size (KB)"])
        self.file_tree.setColumnWidth(0, 140)
        self.file_tree.itemSelectionChanged.connect(self._on_file_selection_changed)  # type: ignore
        splitter.addWidget(self.file_tree)
        # Backward compatibility alias used in early tests (treat tree as list-like)
        self.file_list = self.file_tree  # type: ignore

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
        """Scan the base directory, group HTML assets by logical phase, and populate the tree.

        Grouping is heuristic-based per PHASE_PATTERNS. Files that do not match any
        predicate fall under an "Other" phase bucket. This provides a foundation for
        richer phase-aware operations in subsequent milestones (filtering, batch preview).
        """
        self.file_tree.clear()
        data_root = self._base_dir
        if not os.path.isdir(data_root):  # pragma: no cover - defensive
            return
        pattern = os.path.join(data_root, "**", "*.html")
        files = sorted(glob.glob(pattern, recursive=True))
        # Phase collection
        grouped: dict[str, list[str]] = {pid: [] for pid, _lbl, _ in PHASE_PATTERNS}
        grouped[OTHER_PHASE_ID] = []
        label_map = {pid: lbl for pid, lbl, _ in PHASE_PATTERNS}
        label_map[OTHER_PHASE_ID] = "Other"
        for fpath in files:
            rel = os.path.relpath(fpath, data_root)
            fn = os.path.basename(rel).lower()
            assigned = False
            for pid, _lbl, pred in PHASE_PATTERNS:
                try:
                    if pred(rel, fn):
                        grouped[pid].append(fpath)
                        assigned = True
                        break
                except Exception:
                    pass
            if not assigned:
                grouped[OTHER_PHASE_ID].append(fpath)
        # Build tree
        total_files = 0
        for pid, files_in_phase in grouped.items():
            if not files_in_phase:
                continue
            phase_item = QTreeWidgetItem([label_map.get(pid, pid), "", ""])
            phase_item.setData(0, Qt.ItemDataRole.UserRole, {"phase": pid})
            self.file_tree.addTopLevelItem(phase_item)
            for fpath in sorted(files_in_phase):
                rel = os.path.relpath(fpath, data_root)
                try:
                    stat = os.stat(fpath)
                    size_kb = f"{stat.st_size/1024:.1f}"
                except Exception:
                    size_kb = "?"
                child = QTreeWidgetItem(["", rel, size_kb])
                child.setData(0, Qt.ItemDataRole.UserRole, {"file": fpath, "phase": pid})
                child.setData(1, Qt.ItemDataRole.UserRole, {"file": fpath, "phase": pid})
                phase_item.addChild(child)
                total_files += 1
            phase_item.setExpanded(True)
        self._append_log(
            f"Refreshed: {total_files} HTML files across {sum(1 for v in grouped.values() if v)} phases."
        )

    # ------------------------------------------------------------------
    # Events & Actions
    def _on_file_selection_changed(self) -> None:
        # Enable preview only if a concrete file (child) is selected
        items = self.file_tree.selectedItems()
        enabled = False
        if items:
            data = items[0].data(0, Qt.ItemDataRole.UserRole)
            if isinstance(data, dict) and "file" in data:
                enabled = True
        self.btn_preview.setEnabled(enabled)

    def _on_preview_clicked(self) -> None:
        items = self.file_tree.selectedItems()
        if not items:
            return
        target = items[0]
        payload = target.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(payload, dict) or "file" not in payload:
            return  # phase node selected
        fpath = payload.get("file")
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
            try:
                rel_name = target.text(1) or target.text(0)
            except Exception:
                rel_name = fpath
            self._append_log(f"Previewed: {rel_name}")
        except Exception as e:  # pragma: no cover - unlikely
            self.preview_area.setPlainText(f"Error reading file: {e}")
            try:
                rel_name = target.text(1) or target.text(0)
            except Exception:
                rel_name = "<unknown>"
            self._append_log(f"ERROR preview {rel_name}: {e}")

    # ------------------------------------------------------------------
    # Logging helper
    def _append_log(self, line: str) -> None:
        self.log_area.appendPlainText(line)

    # ------------------------------------------------------------------
    # Accessors used in tests
    def listed_files(self) -> List[str]:
        """Return the relative paths of all discovered files (flattened)."""
        files: list[str] = []
        root_count = self.file_tree.topLevelItemCount()
        for r in range(root_count):
            phase_item = self.file_tree.topLevelItem(r)
            for c in range(phase_item.childCount()):
                child = phase_item.child(c)
                text = child.text(1) or child.text(0)
                if text:
                    files.append(text)
        return files

    def phases(self) -> List[str]:
        """Return list of phase identifiers currently present (with at least one file)."""
        ids: list[str] = []
        for r in range(self.file_tree.topLevelItemCount()):
            item = self.file_tree.topLevelItem(r)
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(data, dict) and "phase" in data:
                ids.append(data["phase"])  # type: ignore[index]
        return ids

    def base_dir(self) -> str:
        return self._base_dir
