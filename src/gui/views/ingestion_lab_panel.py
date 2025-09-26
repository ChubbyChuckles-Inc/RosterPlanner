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
    QLineEdit,
    QCheckBox,
    QMenu,
    QToolButton,
    QSpinBox,
    QStackedLayout,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
import json
from gui.components.theme_aware import ThemeAwareMixin
import sqlite3
import hashlib
from dataclasses import dataclass
from typing import Dict, Any
import time
from PyQt6.QtWidgets import QAbstractItemView

try:  # pragma: no cover - optional import
    from gui.components.skeleton_loader import SkeletonLoaderWidget
except Exception:  # pragma: no cover
    SkeletonLoaderWidget = None  # type: ignore

# Field coverage backend (Milestone 7.10.26)
try:  # pragma: no cover - import guard if module missing in earlier migrations
    from gui.ingestion.rule_field_coverage import compute_field_coverage, FieldCoverageReport
    from gui.ingestion.rule_orphan import compute_orphan_fields
    from gui.ingestion.rule_quality_gates import evaluate_quality_gates
    from gui.ingestion.rule_apply_guard import SafeApplyGuard
except Exception:  # pragma: no cover
    compute_field_coverage = None  # type: ignore
    FieldCoverageReport = None  # type: ignore
    evaluate_quality_gates = None  # type: ignore

# Lazy service locator import (optional; panel should degrade gracefully if unavailable)
try:  # pragma: no cover - import guard
    from gui.services.service_locator import services as _services  # type: ignore
except Exception:  # pragma: no cover - fallback when running isolated
    _services = None  # type: ignore

__all__ = ["IngestionLabPanel", "HashImpactResult"]


@dataclass
class HashImpactResult:
    """Result container for hash impact preview (Milestone 7.10.22).

    Attributes
    ----------
    updated: list[str]
        Existing provenance entries whose current file hash differs (would be re-ingested).
    unchanged: list[str]
        Files whose hash matches provenance (eligible for cached skip path).
    new: list[str]
        Files present on disk but absent from provenance table (first-time ingest).
    missing: list[str]
        Provenance entries referencing files no longer present on disk (stale rows).
    """

    updated: list[str]
    unchanged: list[str]
    new: list[str]
    missing: list[str]

    def summary(self) -> str:  # pragma: no cover - trivial
        return f"Updated {len(self.updated)} | Unchanged {len(self.unchanged)} | New {len(self.new)} | Missing {len(self.missing)}"


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


class IngestionLabPanel(QWidget, ThemeAwareMixin):
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
        # Hash impact & provenance caches (populated on refresh)
        self._last_provenance: dict[str, tuple[str, str, int]] = {}
        self._last_hash_impact: HashImpactResult | None = None
        self.refresh_file_list()
        # Apply initial styling if theme/density services available
        try:
            self._apply_density_and_theme()
        except Exception:
            pass

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
        self.btn_hash_impact = QPushButton("Hash Impact")
        self.btn_hash_impact.setToolTip("Compute which files would trigger ingest (hash changes)")
        self.btn_field_coverage = QPushButton("Field Coverage")
        self.btn_field_coverage.setToolTip(
            "Compute per-field non-empty ratios across all visible files using current rules"
        )
        self.btn_orphan_fields = QPushButton("Orphan Fields")
        self.btn_orphan_fields.setToolTip("List extracted fields lacking mapping entries")
        self.btn_quality_gates = QPushButton("Quality Gates")
        self.btn_quality_gates.setToolTip(
            "Evaluate minimum non-null ratios (quality gate config under 'quality_gates' in rules JSON)"
        )
        self.btn_simulate = QPushButton("Simulate")
        self.btn_simulate.setToolTip(
            "Run safe simulation (adapter + coverage + gates) — no DB writes"
        )
        self.btn_apply = QPushButton("Apply")
        self.btn_apply.setToolTip("Apply last successful simulation (audit only in this milestone)")
        self.btn_versions = QPushButton("Versions")
        self.btn_versions.setToolTip("List stored rule set versions in log")
        self.btn_rollback = QPushButton("Rollback")
        self.btn_rollback.setToolTip("Load previous rule version into editor (not yet applied)")
        self.btn_export = QPushButton("Export")
        self.btn_export.setToolTip("Export current rules to a JSON file")
        self.btn_import = QPushButton("Import")
        self.btn_import.setToolTip("Import rules from a JSON file (replaces editor contents)")
        self.btn_selector_picker = QPushButton("Pick Selector")
        self.btn_selector_picker.setToolTip(
            "Open visual picker to build CSS selector from sample HTML"
        )
        self.btn_regex_tester = QPushButton("Regex Tester")
        self.btn_regex_tester.setToolTip("Open regex tester dialog for pattern experimentation")
        self.btn_derived = QPushButton("Derived Fields")
        self.btn_derived.setToolTip(
            "Compose derived fields (expressions referencing existing extracted fields)"
        )
        self.btn_dep_graph = QPushButton("Dep Graph")
        self.btn_dep_graph.setToolTip("Show dependency graph (base + derived field relationships)")
        self.btn_benchmark = QPushButton("Benchmark")
        self.btn_benchmark.setToolTip(
            "Run A/B parse benchmark comparing two rule variants over a sample of visible files"
        )
        self.btn_cache = QPushButton("Cache Inspect")
        self.btn_cache.setToolTip(
            "Show which files are unchanged (cache hit) vs updated/new/missing based on provenance"
        )
        self.btn_security = QPushButton("Security Scan")
        self.btn_security.setToolTip(
            "Run static security sandbox scan over expression & derived transforms"
        )
        # Draft / publish (7.10.49)
        self.btn_publish = QPushButton("Publish")
        self.btn_publish.setToolTip(
            "Persist current draft rule set as the active published version (creates new version entry if changed)."
        )
        # Search / filter controls (7.10.4)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search filename or hash…")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.setObjectName("ingestionLabSearch")
        # Phase filter popup (multi-select)
        self.phase_filter_button = QToolButton()
        self.phase_filter_button.setText("Phases ▾")
        self.phase_filter_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._phase_menu = QMenu(self)
        self._phase_checks: dict[str, QCheckBox] = {}
        for pid, label, _ in PHASE_PATTERNS + [(OTHER_PHASE_ID, "Other", lambda *_: False)]:
            cb = QCheckBox(label)
            cb.setChecked(True)
            act = self._phase_menu.addAction(label)

            # Embed checkbox state via triggered connection; store mapping
            def _toggle(checked: bool = False, box=cb):  # noqa: ANN001
                box.setChecked(not box.isChecked())  # invert on each action trigger
                self._apply_filters()

            act.triggered.connect(_toggle)  # type: ignore
            self._phase_checks[pid] = cb
        self.phase_filter_button.setMenu(self._phase_menu)
        # Size range (KB)
        self.min_size = QSpinBox()
        self.min_size.setPrefix(">= ")
        self.min_size.setMaximum(10_000)
        self.min_size.setToolTip("Minimum size (KB)")
        self.max_size = QSpinBox()
        self.max_size.setPrefix("<= ")
        self.max_size.setMaximum(10_000)
        self.max_size.setToolTip("Maximum size (KB; 0 = no limit)")
        # Modified since (epoch seconds delta: last N hours) simple heuristic input
        self.modified_within_hours = QSpinBox()
        self.modified_within_hours.setPrefix("< ")
        self.modified_within_hours.setMaximum(720)
        self.modified_within_hours.setToolTip("Show files modified within last N hours (0 = any)")
        actions.addWidget(self.btn_refresh)
        actions.addWidget(self.btn_preview)
        actions.addWidget(self.btn_hash_impact)
        actions.addWidget(self.btn_field_coverage)
        actions.addWidget(self.btn_orphan_fields)
        actions.addWidget(self.btn_quality_gates)
        actions.addWidget(self.btn_simulate)
        actions.addWidget(self.btn_apply)
        actions.addWidget(self.btn_versions)
        actions.addWidget(self.btn_rollback)
        actions.addWidget(self.btn_export)
        actions.addWidget(self.btn_import)
        actions.addWidget(self.btn_selector_picker)
        actions.addWidget(self.btn_regex_tester)
        actions.addWidget(self.btn_derived)
        actions.addWidget(self.btn_dep_graph)
        actions.addWidget(self.btn_benchmark)
        actions.addWidget(self.btn_cache)
        actions.addWidget(self.btn_security)
        actions.addWidget(self.btn_publish)
        actions.addWidget(self.search_box, 1)
        actions.addWidget(self.phase_filter_button)
        actions.addWidget(QLabel("Size KB:"))
        actions.addWidget(self.min_size)
        actions.addWidget(self.max_size)
        actions.addWidget(QLabel("Mod <h:"))
        actions.addWidget(self.modified_within_hours)
        actions.addStretch(1)
        root.addLayout(actions)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        root.addWidget(splitter, 1)

        # Left: File Navigator (grouped). Replace flat list with tree (phase -> files)
        self.file_tree = QTreeWidget()
        self.file_tree.setObjectName("ingestionLabFileTree")
        # Enable multi-selection for batch preview operations (7.10.46)
        try:
            self.file_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        except Exception:
            pass
        # Columns (Milestone 7.10.3): Phase | File | Size (KB) | Hash (short) | Last Ingested | Parser Ver
        self.file_tree.setHeaderLabels(
            ["Phase", "File", "Size (KB)", "Hash", "Last Ingested", "Parser Ver"]
        )
        self.file_tree.setColumnWidth(0, 140)
        self.file_tree.setColumnWidth(2, 70)
        self.file_tree.setColumnWidth(3, 110)
        self.file_tree.setColumnWidth(4, 120)
        self.file_tree.setColumnWidth(5, 70)
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
        # Fallback styling (will be overridden by _apply_density_and_theme if theme service present)
        try:  # pragma: no cover - guarded import
            from gui.services.service_locator import services as _svc

            if not _svc.try_get("theme_service"):
                self.rule_editor.setStyleSheet(
                    "QPlainTextEdit#ingestionLabRuleEditor { background:#1b1b1b; color:#f0f0f0; font-family:Consolas,'Courier New',monospace; font-size:12px; }"
                )
        except Exception:
            self.rule_editor.setStyleSheet(
                "QPlainTextEdit#ingestionLabRuleEditor { background:#1b1b1b; color:#f0f0f0; font-family:Consolas,'Courier New',monospace; font-size:12px; }"
            )
        mid_split.addWidget(self.rule_editor)

        # Preview container (stack: main preview text + batch-loading skeleton) (7.10.46)
        self._preview_container = QWidget()
        self._preview_stack = QStackedLayout(self._preview_container)
        self.preview_area = QTextEdit()
        self.preview_area.setObjectName("ingestionLabPreview")
        self.preview_area.setReadOnly(True)
        self.preview_area.setPlaceholderText("Select a file then click Preview to see metadata.")
        try:  # pragma: no cover
            from gui.services.service_locator import services as _svc

            if not _svc.try_get("theme_service"):
                self.preview_area.setStyleSheet(
                    "QTextEdit#ingestionLabPreview { background:#111111; color:#e0e0e0; font-family:Consolas,'Courier New',monospace; font-size:12px; }"
                )
        except Exception:
            self.preview_area.setStyleSheet(
                "QTextEdit#ingestionLabPreview { background:#111111; color:#e0e0e0; font-family:Consolas,'Courier New',monospace; font-size:12px; }"
            )
        self._preview_stack.addWidget(self.preview_area)  # index 0
        # Batch skeleton (rows adapt later); only if loader component available
        if SkeletonLoaderWidget:
            self._batch_skeleton = SkeletonLoaderWidget("table-row", rows=4, shimmer=True)
            self._preview_stack.addWidget(self._batch_skeleton)  # index 1
        else:  # pragma: no cover - fallback placeholder label
            ph = QLabel("Loading batch preview…")
            ph.setObjectName("ingestionLabBatchFallback")
            self._batch_skeleton = ph  # type: ignore
            self._preview_stack.addWidget(ph)
        self._preview_stack.setCurrentIndex(0)
        mid_split.addWidget(self._preview_container)

        # Right: Execution Log
        self.log_area = QPlainTextEdit()
        self.log_area.setObjectName("ingestionLabLog")
        self.log_area.setReadOnly(True)
        self.log_area.setPlaceholderText(
            "Execution log will appear here (rule validation, parse results)."
        )
        try:  # pragma: no cover
            from gui.services.service_locator import services as _svc

            if not _svc.try_get("theme_service"):
                self.log_area.setStyleSheet(
                    "QPlainTextEdit#ingestionLabLog { background:#141414; color:#d0d0d0; font-family:Consolas,'Courier New',monospace; font-size:12px; }"
                )
        except Exception:
            self.log_area.setStyleSheet(
                "QPlainTextEdit#ingestionLabLog { background:#141414; color:#d0d0d0; font-family:Consolas,'Courier New',monospace; font-size:12px; }"
            )
        splitter.addWidget(self.log_area)

        splitter.setStretchFactor(0, 25)
        splitter.setStretchFactor(1, 45)
        splitter.setStretchFactor(2, 30)

        # Connections
        self.btn_refresh.clicked.connect(self.refresh_file_list)  # type: ignore
        self.btn_preview.clicked.connect(self._on_preview_clicked)  # type: ignore
        self.btn_hash_impact.clicked.connect(self._on_hash_impact_clicked)  # type: ignore
        self.btn_field_coverage.clicked.connect(self._on_field_coverage_clicked)  # type: ignore
        self.btn_orphan_fields.clicked.connect(self._on_orphan_fields_clicked)  # type: ignore
        self.btn_quality_gates.clicked.connect(self._on_quality_gates_clicked)  # type: ignore
        self.btn_simulate.clicked.connect(self._on_simulate_clicked)  # type: ignore
        self.btn_apply.clicked.connect(self._on_apply_clicked)  # type: ignore
        self.btn_versions.clicked.connect(self._on_versions_clicked)  # type: ignore
        self.btn_rollback.clicked.connect(self._on_rollback_clicked)  # type: ignore
        self.btn_export.clicked.connect(self._on_export_rules_clicked)  # type: ignore
        self.btn_import.clicked.connect(self._on_import_rules_clicked)  # type: ignore
        self.btn_selector_picker.clicked.connect(self._on_selector_picker_clicked)  # type: ignore
        self.btn_regex_tester.clicked.connect(self._on_regex_tester_clicked)  # type: ignore
        self.btn_derived.clicked.connect(self._on_derived_fields_clicked)  # type: ignore
        self.btn_dep_graph.clicked.connect(self._on_dependency_graph_clicked)  # type: ignore
        self.btn_benchmark.clicked.connect(self._on_benchmark_clicked)  # type: ignore
        self.btn_cache.clicked.connect(self._on_cache_inspector_clicked)  # type: ignore
        self.btn_security.clicked.connect(self._on_security_scan_clicked)  # type: ignore
        self.btn_publish.clicked.connect(self._on_publish_clicked)  # type: ignore
        self.search_box.textChanged.connect(lambda _t: self._apply_filters())  # type: ignore
        self.min_size.valueChanged.connect(lambda _v: self._apply_filters())  # type: ignore
        self.max_size.valueChanged.connect(lambda _v: self._apply_filters())  # type: ignore
        self.modified_within_hours.valueChanged.connect(lambda _v: self._apply_filters())  # type: ignore

        # Internal cache of all file items for filtering without re-scanning
        # Holds all leaf file items for filtering purposes
        self._all_file_items = []  # list of file QTreeWidgetItem
        # Cache last field coverage report for tests (Milestone 7.10.26)
        self._last_field_coverage = None  # type: ignore[assignment]
        # Safe apply guard state (7.10.30/31)
        try:
            self._safe_guard = SafeApplyGuard()
        except Exception:  # pragma: no cover
            self._safe_guard = None
        self._last_simulation_id = None
        # Inline banner label for post-apply summary (7.10.31)
        self._banner = QLabel("")
        self._banner.setObjectName("ingestionLabBanner")
        self._banner.setStyleSheet(
            "#ingestionLabBanner { border:1px solid #888; padding:4px; border-radius:4px; background: rgba(200,200,200,0.15); }"
        )
        self._banner.setVisible(False)
        root.insertWidget(0, self._banner)
        self._last_apply_summary = {}
        self._last_version_num = None  # Version store tracking
        # Inline performance badge (7.10.45)
        # Performance threshold now sourced from settings service if available (7.10.50)
        try:  # late import to avoid circulars
            from gui.services.settings_service import SettingsService  # type: ignore

            self.preview_perf_threshold_ms = float(
                getattr(
                    SettingsService.instance,
                    "ingestion_preview_perf_threshold_ms",
                    float(os.environ.get("RP_ING_PREVIEW_PERF_THRESHOLD_MS", "120")),
                )
            )
        except Exception:
            self.preview_perf_threshold_ms = float(
                os.environ.get("RP_ING_PREVIEW_PERF_THRESHOLD_MS", "120")
            )  # fallback
        self._perf_badge = QLabel("")
        self._perf_badge.setObjectName("ingestionLabPerfBadge")
        self._perf_badge.setStyleSheet(
            "#ingestionLabPerfBadge { border:1px solid #c77; background:rgba(200,40,40,0.15);"
            " padding:2px 6px; border-radius:4px; font-size:11px; color:#a00; }"
        )
        self._perf_badge.setVisible(False)
        self._perf_badge_active = False
        root.insertWidget(1, self._perf_badge)
        self._register_shortcuts()
        self._configure_keyboard_focus()
        # Draft autosave (7.10.49)
        self._draft_path = os.path.join(self._base_dir, ".ingestion_rules_draft.json")
        self._last_published_hash = None
        self._draft_autosave_interval_ms = int(os.environ.get("RP_ING_DRAFT_AUTOSAVE_MS", "5000"))
        self._draft_dirty = False
        try:
            from PyQt6.QtCore import QTimer

            self._draft_timer = QTimer(self)
            self._draft_timer.setInterval(self._draft_autosave_interval_ms)
            self._draft_timer.timeout.connect(self._autosave_draft)  # type: ignore
            self._draft_timer.start()
        except Exception:  # pragma: no cover
            self._draft_timer = None  # type: ignore
        self.rule_editor.textChanged.connect(self._on_rule_text_changed)  # type: ignore
        self._load_existing_draft()
        # Batch preview configuration (env overrides for tests) (7.10.46)
        self.batch_preview_skeleton_min_files = int(
            os.environ.get("RP_ING_BATCH_SKELETON_MIN_FILES", "5")
        )
        self.batch_preview_artificial_delay_ms = int(os.environ.get("RP_ING_BATCH_DELAY_MS", "0"))
        self._batch_skeleton_last_shown = False  # test visibility flag

    # ------------------------------------------------------------------
    # File Discovery
    def refresh_file_list(self) -> None:
        """Scan the base directory, group HTML assets by logical phase, and populate the tree.

        Grouping is heuristic-based per PHASE_PATTERNS. Files that do not match any
        predicate fall under an "Other" phase bucket. This provides a foundation for
        richer phase-aware operations in subsequent milestones (filtering, batch preview).
        """
        self.file_tree.clear()
        self._all_file_items.clear()
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

        # Provenance map: path -> (sha1, last_ingested_at, parser_version)
        provenance: dict[str, tuple[str, str, int]] = {}
        conn: sqlite3.Connection | None = None
        if _services is not None:
            try:
                conn = _services.try_get("sqlite_conn")  # type: ignore[attr-defined]
            except Exception:  # pragma: no cover - defensive
                conn = None
        if conn is not None:
            try:
                cur = conn.execute(
                    "SELECT path, sha1, COALESCE(last_ingested_at,'') as ts, COALESCE(parser_version,1) FROM provenance"
                )
                for row in cur.fetchall():
                    provenance[str(row[0])] = (str(row[1]), str(row[2]), int(row[3]))
            except Exception:  # pragma: no cover - provenance optional
                provenance = {}

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
            phase_item = QTreeWidgetItem([label_map.get(pid, pid), "", "", "", "", ""])
            phase_item.setData(0, Qt.ItemDataRole.UserRole, {"phase": pid})
            self.file_tree.addTopLevelItem(phase_item)
            for fpath in sorted(files_in_phase):
                rel = os.path.relpath(fpath, data_root)
                try:
                    stat = os.stat(fpath)
                    size_kb = f"{stat.st_size/1024:.1f}"
                except Exception:
                    size_kb = "?"
                prov = provenance.get(fpath)
                if prov:
                    sha1, ts, parser_ver = prov
                    short_hash = sha1[:10]
                else:
                    short_hash = ""  # Not yet ingested
                    ts = ""
                    parser_ver = 0
                child = QTreeWidgetItem(
                    ["", rel, size_kb, short_hash, ts, str(parser_ver) if parser_ver else "-"]
                )
                child.setData(0, Qt.ItemDataRole.UserRole, {"file": fpath, "phase": pid})
                child.setData(1, Qt.ItemDataRole.UserRole, {"file": fpath, "phase": pid})
                # Store full provenance metadata in role for later preview enrichment
                child.setData(
                    2,
                    Qt.ItemDataRole.UserRole,
                    {
                        "file": fpath,
                        "phase": pid,
                        "hash": prov[0] if prov else None,
                        "last_ingested_at": ts if prov else None,
                        "parser_version": parser_ver if prov else None,
                    },
                )
                phase_item.addChild(child)
                self._all_file_items.append(child)
                total_files += 1
            phase_item.setExpanded(True)
        self._last_provenance = provenance
        self._append_log(
            f"Refreshed: {total_files} HTML files across {sum(1 for v in grouped.values() if v)} phases."
        )
        # Re-apply current filters after rebuild
        self._apply_filters()

    # ------------------------------------------------------------------
    # Keyboard-First Workflow (7.10.43)
    def _register_shortcuts(self) -> None:
        """Register keyboard shortcuts for primary panel operations.

        Uses existing global shortcut registry (indirectly via MainWindow cheat sheet)
        but binds QShortcuts locally for panel-scoped actions.
        """
        try:
            from gui.services.shortcut_registry import global_shortcut_registry as _reg
        except Exception:  # pragma: no cover
            _reg = None

        def _reg_if(id_: str, seq: str, desc: str):
            if _reg:
                _reg.register(id_, seq, desc, category="Ingestion Lab")
            QShortcut(QKeySequence(seq), self, activated=lambda: self._dispatch_shortcut(id_))

        _reg_if("ing.refresh", "F5", "Refresh file list")
        _reg_if("ing.preview", "Enter", "Preview selected file")
        _reg_if("ing.search", "Ctrl+F", "Focus search box")
        _reg_if("ing.simulate", "Ctrl+R", "Run simulation")
        _reg_if("ing.apply", "Ctrl+Shift+A", "Apply last simulation")
        _reg_if("ing.security", "Ctrl+Shift+S", "Run security scan")
        _reg_if("ing.export", "Ctrl+E", "Export rules JSON")
        _reg_if("ing.import", "Ctrl+Shift+E", "Import rules JSON")
        _reg_if("ing.hash_impact", "Ctrl+H", "Compute hash impact preview")
        _reg_if("ing.publish", "Ctrl+B", "Publish current draft rule set")

    def _dispatch_shortcut(self, sid: str) -> None:  # pragma: no cover - thin dispatcher
        mapping = {
            "ing.refresh": self.refresh_file_list,
            "ing.preview": self._on_preview_clicked,
            "ing.search": lambda: self.search_box.setFocus(),
            "ing.simulate": self._on_simulate_clicked,
            "ing.apply": self._on_apply_clicked,
            "ing.security": self._on_security_scan_clicked,
            "ing.export": self._on_export_rules_clicked,
            "ing.import": self._on_import_rules_clicked,
            "ing.hash_impact": self._on_hash_impact_clicked,
            "ing.publish": self._on_publish_clicked,
        }
        fn = mapping.get(sid)
        if fn:
            try:
                fn()
            except Exception as e:  # pragma: no cover
                self._append_log(f"Shortcut '{sid}' failed: {e}")

    def _configure_keyboard_focus(self) -> None:
        """Configure initial focus and arrow key navigation for file tree -> editor -> preview.

        Basic behavior:
         - When Enter pressed in file tree it triggers preview.
         - Tab cycles through file tree -> rule editor -> preview -> search -> back.
        """
        # Hook Enter on file_tree
        self.file_tree.keyPressEvent = self._wrap_tree_keypress(self.file_tree.keyPressEvent)

    def _wrap_tree_keypress(self, original):  # pragma: no cover - GUI event path
        def _handler(event):
            try:
                from PyQt6.QtGui import QKeyEvent
            except Exception:  # pragma: no cover
                return original(event)
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._on_preview_clicked()
                return
            return original(event)

        return _handler

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
        items = [
            it
            for it in self.file_tree.selectedItems()
            if isinstance(it.data(0, Qt.ItemDataRole.UserRole), dict)
            and "file" in it.data(0, Qt.ItemDataRole.UserRole)
        ]
        if not items:
            return
        if len(items) == 1:
            self._single_preview(items[0])
        else:
            self._batch_preview(items)

    # ------------------------------------------------------------------
    # Single-file preview (refactored from _on_preview_clicked) (7.10.46)
    def _single_preview(self, target) -> None:
        start = self._now()
        payload = target.data(0, Qt.ItemDataRole.UserRole)
        fpath = payload.get("file")
        try:
            stat = os.stat(fpath)
            with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                snippet = fh.read(800)
            prov_payload = target.data(2, Qt.ItemDataRole.UserRole) or {}
            if isinstance(prov_payload, dict):
                hash_full = prov_payload.get("hash")
                last_ingested = prov_payload.get("last_ingested_at")
                parser_ver = prov_payload.get("parser_version")
            else:  # pragma: no cover
                hash_full = last_ingested = parser_ver = None
            meta = [
                f"File: {fpath}",
                f"Size: {stat.st_size} bytes",
                f"Modified: {int(stat.st_mtime)} (epoch)",
            ]
            if hash_full:
                meta.append(f"Hash: {hash_full}")
            if last_ingested:
                meta.append(f"Last Ingested: {last_ingested}")
            if parser_ver:
                meta.append(f"Parser Version: {parser_ver}")
            meta.extend(["--- Snippet ---", snippet])
            self.preview_area.setPlainText("\n".join(meta))
            try:
                rel_name = target.text(1) or target.text(0)
            except Exception:
                rel_name = fpath
            self._append_log(f"Previewed: {rel_name}")
        except Exception as e:  # pragma: no cover
            self.preview_area.setPlainText(f"Error reading file: {e}")
            try:
                rel_name = target.text(1) or target.text(0)
            except Exception:
                rel_name = "<unknown>"
            self._append_log(f"ERROR preview {rel_name}: {e}")
        elapsed_ms = (self._now() - start) * 1000.0
        self._update_performance_badge(elapsed_ms)
        # Telemetry: record preview
        try:
            from gui.services.telemetry_service import TelemetryService  # type: ignore

            TelemetryService.instance.record_preview(elapsed_ms)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Batch preview with loading skeleton (7.10.46)
    def _batch_preview(self, targets: list) -> None:
        start = self._now()
        count = len(targets)
        use_skeleton = count >= self.batch_preview_skeleton_min_files
        if use_skeleton:
            try:
                # Resize skeleton rows if widget supports simple API
                if hasattr(self._batch_skeleton, "_rows") and hasattr(
                    self._batch_skeleton, "start"
                ):
                    self._preview_stack.setCurrentIndex(1)
                    self._batch_skeleton_last_shown = True
                    if hasattr(self._batch_skeleton, "start"):
                        try:
                            self._batch_skeleton.start()  # type: ignore[attr-defined]
                        except Exception:
                            pass
            except Exception:
                pass
        out_lines = [f"Batch Preview ({count} files)"]
        # Cap batch lines using settings (default 50)
        try:
            from gui.services.settings_service import SettingsService  # type: ignore

            cap = int(getattr(SettingsService.instance, "ingestion_preview_batch_cap", 50))
        except Exception:
            cap = 50
        for idx, it in enumerate(targets[:cap]):  # cap to avoid excessive UI size
            payload = it.data(0, Qt.ItemDataRole.UserRole)
            fpath = payload.get("file") if isinstance(payload, dict) else None
            if not fpath:
                continue
            try:
                stat = os.stat(fpath)
                with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                    snippet = fh.read(200)
                out_lines.append(
                    f"[{idx+1}] {fpath} size={stat.st_size} mod={int(stat.st_mtime)} bytes snippet_len={len(snippet)}"
                )
            except Exception as e:  # pragma: no cover
                out_lines.append(f"[{idx+1}] {fpath} ERROR: {e}")
        if count > cap:
            out_lines.append(f"... truncated {count-cap} more")
        # Artificial delay to allow skeleton perceptibility in tests / UX (optional)
        delay_ms = self.batch_preview_artificial_delay_ms
        if use_skeleton and delay_ms > 0:
            target_t = start + (delay_ms / 1000.0)
            while self._now() < target_t:
                try:
                    from PyQt6.QtWidgets import QApplication

                    QApplication.processEvents()
                except Exception:
                    break
        self.preview_area.setPlainText("\n".join(out_lines))
        if use_skeleton:
            try:
                if hasattr(self._batch_skeleton, "stop"):
                    self._batch_skeleton.stop()  # type: ignore[attr-defined]
            except Exception:
                pass
            self._preview_stack.setCurrentIndex(0)
        self._append_log(f"Batch preview complete: {count} files")
        elapsed_ms = (self._now() - start) * 1000.0
        self._update_performance_badge(elapsed_ms)
        try:  # telemetry
            from gui.services.telemetry_service import TelemetryService  # type: ignore

            TelemetryService.instance.record_preview(elapsed_ms)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Logging helper
    def _append_log(self, line: str) -> None:
        self.log_area.appendPlainText(line)
        # Publish structured events for Logs Dock filtering (7.10.65)
        try:  # pragma: no cover - robustness
            from gui.services.service_locator import services as _services
            from gui.services.event_bus import GUIEvent, EventBus

            bus: EventBus | None = _services.try_get("event_bus")
            if not bus:
                return
            if "Rule validation failed" in line or line.startswith("Rule validation failed"):
                bus.publish(GUIEvent.RULE_VALIDATION_FAILED, {"error": line})
            # Could expand with categorization heuristics later.
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Hash Impact Preview (7.10.22)
    def _on_hash_impact_clicked(self) -> None:
        try:
            res = self.compute_hash_impact()
        except Exception as e:  # pragma: no cover - defensive
            self._append_log(f"Hash Impact ERROR: {e}")
            return
        self._append_log(
            f"Hash Impact: Updated {len(res.updated)} | Unchanged {len(res.unchanged)} | New {len(res.new)} | Missing {len(res.missing)}"
        )

        # Provide a concise listing (first few) to aid user
        def _sample(label: str, items: list[str]):  # noqa: ANN001
            if not items:
                return
            preview = ", ".join(os.path.basename(p) for p in items[:5])
            more = "" if len(items) <= 5 else f" (+{len(items)-5} more)"
            self._append_log(f"  {label}: {preview}{more}")

        _sample("Updated", res.updated)
        _sample("New", res.new)
        _sample("Missing", res.missing)

    def compute_hash_impact(self) -> HashImpactResult:
        """Compute hash impact vs provenance and cache result.

        Returns
        -------
        HashImpactResult
            Categorization of files for potential ingest operations.
        """
        # Gather provenance (fresh if available)
        prov = dict(self._last_provenance)
        # Collect current files from navigator (absolute paths stored in user role)
        current_paths: list[str] = []
        for item in self._all_file_items:
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(data, dict) and "file" in data:
                current_paths.append(data["file"])  # type: ignore[index]
        current_set = set(current_paths)
        missing = [p for p in prov.keys() if p not in current_set]
        updated: list[str] = []
        unchanged: list[str] = []
        new: list[str] = []
        # Build hashes for current files
        for path in current_paths:
            try:
                with open(path, "rb") as fh:
                    content = fh.read()
                sha1 = hashlib.sha1(content).hexdigest()
            except Exception:
                # Treat unreadable files as missing (skip)
                if path in prov:
                    missing.append(path)
                continue
            if path in prov:
                old_sha, _ts, _pv = prov[path]
                if old_sha != sha1:
                    updated.append(path)
                else:
                    unchanged.append(path)
            else:
                new.append(path)
        res = HashImpactResult(
            updated=sorted(updated),
            unchanged=sorted(unchanged),
            new=sorted(new),
            missing=sorted(set(missing)),
        )
        self._last_hash_impact = res
        return res

    def hash_impact_snapshot(self) -> Dict[str, Any]:  # for tests
        if not self._last_hash_impact:
            return {}
        r = self._last_hash_impact
        return {
            "updated": list(r.updated),
            "unchanged": list(r.unchanged),
            "new": list(r.new),
            "missing": list(r.missing),
        }

    # ------------------------------------------------------------------
    # Field Coverage (7.10.26)
    def _gather_visible_file_html(self) -> Dict[str, str]:
        files: Dict[str, str] = {}
        for item in self._all_file_items:
            if item.isHidden():
                continue
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if not (isinstance(data, dict) and "file" in data):
                continue
            path = data.get("file")  # type: ignore[index]
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    files[path] = fh.read()
            except Exception:
                continue
        return files

    def _parse_ruleset_from_editor(self):  # type: ignore[override]
        """Parse the current rule editor content into a RuleSet or raise.

        Supports JSON first; if JSON parse fails, attempts very naive YAML fallback
        (by leveraging json after replacing single quotes & ensuring braces). For
        early milestones we keep implementation minimal.
        """
        from gui.ingestion.rule_schema import RuleSet, RuleError  # local import to avoid cycle

        text = (self.rule_editor.toPlainText() or "").strip()
        if not text:
            raise ValueError("Rule editor is empty – cannot compute coverage")
        try:
            data = json.loads(text)
        except Exception as e_json:
            # Extremely naive YAML-ish fallback: reject for now to keep deterministic
            raise ValueError(f"Failed to parse rules JSON: {e_json}")
        try:
            return RuleSet.from_mapping(data)
        except RuleError as e:  # pragma: no cover - validation path
            raise ValueError(f"Invalid rule set: {e}") from e

    def _on_field_coverage_clicked(self) -> None:
        if compute_field_coverage is None:  # pragma: no cover
            self._append_log("Field Coverage backend unavailable")
            return
        try:
            rs = self._parse_ruleset_from_editor()
        except Exception as e:
            self._append_log(f"Coverage ERROR (rules): {e}")
            return
        html_map = self._gather_visible_file_html()
        if not html_map:
            self._append_log("Coverage: No visible files to analyze")
            return
        try:
            report = compute_field_coverage(rs, html_map)
        except Exception as e:  # pragma: no cover - defensive
            self._append_log(f"Coverage ERROR (compute): {e}")
            return
        self._last_field_coverage = report
        # Summarize in log (compact for test assertions)
        self._append_log(
            f"Field Coverage Overall: {report.overall_ratio:.2%} across {report.total_target_columns} columns"
        )
        for res in report.resources:
            miss = res.missing_columns()
            miss_txt = f" missing={','.join(miss)}" if miss else ""
            self._append_log(
                f"  {res.resource}: avg={res.average_coverage:.2%} fields={len(res.fields)}{miss_txt}"
            )
        # Provide a trailing separator for readability
        self._append_log("— end coverage —")

    # For tests
    def field_coverage_snapshot(self) -> Dict[str, Any]:
        if not self._last_field_coverage:
            return {}
        return self._last_field_coverage.to_mapping()  # type: ignore[no-any-return]

    # ------------------------------------------------------------------
    # Orphan Field Detector (7.10.27)
    def _on_orphan_fields_clicked(self) -> None:
        try:
            rs = self._parse_ruleset_from_editor()
        except Exception as e:
            self._append_log(f"Orphan ERROR (rules): {e}")
            return
        # Attempt to derive a mapping block from editor JSON if present under key 'mapping'
        import json as _json

        raw_text = (self.rule_editor.toPlainText() or "").strip()
        mapping_block = None
        try:
            js = _json.loads(raw_text)
            mapping_block = js.get("mapping") if isinstance(js, dict) else None
            if mapping_block is not None and not isinstance(mapping_block, dict):
                mapping_block = None
        except Exception:
            mapping_block = None
        try:
            orphans = compute_orphan_fields(rs, mapping_block)
        except Exception as e:  # pragma: no cover
            self._append_log(f"Orphan ERROR (compute): {e}")
            return
        if not orphans:
            self._append_log("Orphans: none")
            return
        self._append_log(f"Orphans ({len(orphans)}):")
        for o in orphans[:25]:  # cap log spam
            self._append_log(f"  {o.resource}.{o.field} -> {o.suggestion}")
        if len(orphans) > 25:
            self._append_log(f"  ... {len(orphans)-25} more")

    # ------------------------------------------------------------------
    # Quality Gates (7.10.28)
    def _on_quality_gates_clicked(self) -> None:
        if evaluate_quality_gates is None:  # pragma: no cover
            self._append_log("Quality Gates backend unavailable")
            return
        try:
            rs = self._parse_ruleset_from_editor()
        except Exception as e:
            self._append_log(f"Quality Gates ERROR (rules): {e}")
            return
        import json as _json

        text = (self.rule_editor.toPlainText() or "").strip()
        gates_cfg = {}
        try:
            js = _json.loads(text)
            gates_cfg = js.get("quality_gates", {}) if isinstance(js, dict) else {}
            if not isinstance(gates_cfg, dict):
                gates_cfg = {}
        except Exception:
            gates_cfg = {}
        if not gates_cfg:
            self._append_log("Quality Gates: no 'quality_gates' config block present")
            return
        html_map = self._gather_visible_file_html()
        if not html_map:
            self._append_log("Quality Gates: no visible files")
            return
        try:
            report = evaluate_quality_gates(rs, html_map, gates_cfg)
        except Exception as e:  # pragma: no cover
            self._append_log(f"Quality Gates ERROR (compute): {e}")
            return
        status = "PASS" if report.passed else f"FAIL ({report.failed_count} failing)"
        self._append_log(f"Quality Gates Result: {status}")
        for r in report.results[:50]:
            mark = "✅" if r.passed else "❌"
            self._append_log(
                f"  {mark} {r.resource}.{r.field} ratio={r.ratio:.2%} threshold={r.threshold:.2%}"
            )
        if len(report.results) > 50:
            self._append_log(f"  ... {len(report.results)-50} more")

    # ------------------------------------------------------------------
    # Simulation / Apply (7.10.30 / 7.10.31)
    def _on_simulate_clicked(self) -> None:
        if not self._safe_guard:
            self._append_log("Simulate: guard unavailable")
            return
        try:
            rs = self._parse_ruleset_from_editor()
        except Exception as e:
            self._append_log(f"Simulate ERROR (rules): {e}")
            return
        import json as _json

        text = (self.rule_editor.toPlainText() or "").strip()
        try:
            raw_payload = _json.loads(text)
            if not isinstance(raw_payload, dict):
                raw_payload = {}
        except Exception:
            raw_payload = {}
        html_map = self._gather_visible_file_html()
        if not html_map:
            self._append_log("Simulate: no visible files")
            return
        try:
            sim = self._safe_guard.simulate(rs, html_map, raw_payload)
        except Exception as e:  # pragma: no cover
            self._append_log(f"Simulate ERROR: {e}")
            return
        self._last_simulation_id = sim.sim_id
        status = "PASS" if sim.passed else "FAIL"
        self._append_log(
            f"Simulation {sim.sim_id} {status}: rows={sum(sim.adapter_rows.values())} resources={len(sim.adapter_rows)}"
        )
        if sim.reasons:
            for r in sim.reasons[:10]:
                self._append_log(f"  reason: {r}")
            if len(sim.reasons) > 10:
                self._append_log(f"  ... {len(sim.reasons)-10} more")
        self._banner.setVisible(False)

    def _on_apply_clicked(self) -> None:
        if not self._safe_guard:
            self._append_log("Apply: guard unavailable")
            return
        if self._last_simulation_id is None:
            self._append_log("Apply: no prior simulation")
            return
        # Acquire connection from services if available; else create transient in-memory
        conn = None
        if _services is not None:
            try:
                conn = _services.try_get("sqlite_conn")
            except Exception:
                conn = None
        import sqlite3 as _sqlite3

        if conn is None:
            try:
                conn = _sqlite3.connect(":memory:")
            except Exception:
                self._append_log("Apply ERROR: no DB connection available")
                return
        # Reparse rules payload for hash consistency
        import json as _json

        text = (self.rule_editor.toPlainText() or "").strip()
        try:
            raw_payload = _json.loads(text)
            if not isinstance(raw_payload, dict):
                raw_payload = {}
        except Exception:
            raw_payload = {}
        try:
            rs = self._parse_ruleset_from_editor()
        except Exception as e:
            self._append_log(f"Apply ERROR (rules): {e}")
            return
        html_map = self._gather_visible_file_html()
        if not html_map:
            self._append_log("Apply: no visible files")
            return
        try:
            result = self._safe_guard.apply(
                self._last_simulation_id, rs, html_map, raw_payload, conn
            )
        except Exception as e:
            self._append_log(f"Apply ERROR: {e}")
            return
        # Versioning (Milestone 7.10.33 initial storage)
        from gui.ingestion.rule_versioning import RuleSetVersionStore

        try:
            store = RuleSetVersionStore(conn)
            self._last_version_num = store.save_version(raw_payload, text or "{}")
        except Exception as ve:  # pragma: no cover
            self._append_log(f"Versioning WARN: {ve}")
        # Persist rule_version into provenance for affected files (Milestone 7.10.34)
        if self._last_version_num:
            try:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS provenance(path TEXT PRIMARY KEY, sha1 TEXT NOT NULL, last_ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, parser_version INTEGER DEFAULT 1, rule_version INTEGER DEFAULT NULL)"
                )
                # Ensure column exists (migration) then update
                try:
                    cur = conn.execute("PRAGMA table_info(provenance)")
                    cols = {r[1] for r in cur.fetchall()}
                    if "rule_version" not in cols:
                        conn.execute(
                            "ALTER TABLE provenance ADD COLUMN rule_version INTEGER DEFAULT NULL"
                        )
                except Exception:
                    pass
                # Compute hashes for involved files to keep provenance coherent
                import hashlib as _hl

                for fpath, html in html_map.items():
                    sha1 = _hl.sha1(html.encode("utf-8", "ignore")).hexdigest()
                    conn.execute(
                        "INSERT INTO provenance(path, sha1, last_ingested_at, rule_version) VALUES(?,?,CURRENT_TIMESTAMP, ?) "
                        "ON CONFLICT(path) DO UPDATE SET sha1=excluded.sha1, last_ingested_at=CURRENT_TIMESTAMP, rule_version=excluded.rule_version",
                        (fpath, sha1, self._last_version_num),
                    )
                conn.commit()
            except Exception as pe:  # pragma: no cover
                self._append_log(f"Provenance rule_version WARN: {pe}")
        # Build summary (unchanged/skipped placeholders for now)
        inserted_total = sum(result.rows_by_resource.values())
        summary_text = f"Apply Summary sim={result.sim_id} inserted_rows={inserted_total} resources={len(result.rows_by_resource)}"
        self._banner.setText(summary_text)
        self._banner.setVisible(True)
        self._last_apply_summary = {
            "sim_id": result.sim_id,
            "inserted_total": inserted_total,
            "rows_by_resource": dict(result.rows_by_resource),
        }
        self._append_log(summary_text)
        if self._last_version_num:
            self._append_log(f"Rule Version: v{self._last_version_num}")
        # Telemetry: record successful apply
        try:
            from gui.services.telemetry_service import TelemetryService  # type: ignore

            TelemetryService.instance.record_apply()
        except Exception:
            pass
        # Emit event (Milestone 7.10.32) if event bus available
        if _services is not None:
            try:
                from gui.services.event_bus import GUIEvent, EventBus  # local import

                bus: EventBus | None = _services.try_get("event_bus")
                if bus:
                    bus.publish(
                        GUIEvent.INGEST_RULES_APPLIED,
                        {
                            "sim_id": result.sim_id,
                            "inserted_total": inserted_total,
                            "rows_by_resource": dict(result.rows_by_resource),
                        },
                    )
            except Exception:  # pragma: no cover - event emission is best effort
                pass

    # Snapshot for tests
    def apply_summary_snapshot(self) -> Dict[str, Any]:  # pragma: no cover - test helper
        return dict(self._last_apply_summary)

    # ------------------------------------------------------------------
    # Selector Picker (7.10.35 initial)
    def _on_selector_picker_clicked(self) -> None:
        # Choose currently selected file's HTML as context (or first visible file)
        target_file = None
        items = self.file_tree.selectedItems()
        if items:
            data = items[0].data(0, Qt.ItemDataRole.UserRole)
            if isinstance(data, dict) and data.get("file"):
                target_file = data.get("file")
        if not target_file:
            for it in self._all_file_items:
                if not it.isHidden():
                    d = it.data(0, Qt.ItemDataRole.UserRole)
                    if isinstance(d, dict) and d.get("file"):
                        target_file = d.get("file")
                        break
        if not target_file:
            self._append_log("Selector Picker: no file available")
            return
        try:
            with open(target_file, "r", encoding="utf-8", errors="replace") as fh:
                html = fh.read()
        except Exception as e:  # pragma: no cover
            self._append_log(f"Selector Picker ERROR: {e}")
            return
        try:
            from gui.ingestion.selector_picker import SelectorPickerDialog
        except Exception as e:  # pragma: no cover
            self._append_log(f"Selector Picker import failed: {e}")
            return
        dlg = SelectorPickerDialog(html, self)
        if dlg.exec() == dlg.DialogCode.Accepted:  # type: ignore
            sel = dlg.selected_selector()
            if not sel:
                self._append_log("Selector Picker: no selection made")
                return
            # Insert or append into rule editor at cursor position (simple heuristic)
            cursor = self.rule_editor.textCursor()
            insertion = f"\n# selector-picked\nselector: '{sel}'\n"
            cursor.insertText(insertion)
            self._append_log(f"Selector Picker inserted: {sel}")

    # ------------------------------------------------------------------
    # Regex Tester (7.10.36 initial)
    def _on_regex_tester_clicked(self) -> None:
        # Use currently previewed text or first visible file snippet as sample
        sample = self.preview_area.toPlainText() or ""
        if not sample:
            # Attempt to load first visible file snippet
            for it in self._all_file_items:
                if it.isHidden():
                    continue
                data = it.data(0, Qt.ItemDataRole.UserRole)
                if isinstance(data, dict) and data.get("file"):
                    try:
                        with open(data.get("file"), "r", encoding="utf-8", errors="replace") as fh:
                            sample = fh.read(1200)
                    except Exception:
                        sample = ""
                    break
        try:
            from gui.ingestion.regex_tester import RegexTesterDialog
        except Exception as e:  # pragma: no cover
            self._append_log(f"Regex Tester import failed: {e}")
            return
        dlg = RegexTesterDialog(sample_text=sample, parent=self)
        dlg.exec()
        # (No direct side effect into rules; purely exploratory tool.)

    # ------------------------------------------------------------------
    # Derived Field Composer (7.10.37 initial)
    def _on_derived_fields_clicked(self) -> None:
        try:
            from gui.ingestion.derived_field_composer import (
                DerivedFieldComposerDialog,
                update_ruleset_with_derived,
            )
        except Exception as e:  # pragma: no cover
            self._append_log(f"Derived Fields import failed: {e}")
            return
        rules_txt = self.rule_editor.toPlainText()
        dlg = DerivedFieldComposerDialog(rules_txt, self)
        if dlg.exec() != dlg.DialogCode.Accepted:  # type: ignore[attr-defined]
            self._append_log("Derived Fields: cancelled")
            return
        derived_map = dlg.derived_fields()
        if not derived_map:
            self._append_log("Derived Fields: none added")
            return
        try:
            new_text = update_ruleset_with_derived(rules_txt, derived_map)
        except Exception as e:  # pragma: no cover
            self._append_log(f"Derived Fields update failed: {e}")
            return
        self.rule_editor.setPlainText(new_text)
        self._append_log("Derived Fields added: " + ", ".join(sorted(derived_map.keys())))

    # ------------------------------------------------------------------
    # Dependency Graph Viewer (7.10.38 initial)
    def _on_dependency_graph_clicked(self) -> None:
        try:
            from gui.ingestion.dependency_graph import DependencyGraphDialog
        except Exception as e:  # pragma: no cover
            self._append_log(f"Dep Graph import failed: {e}")
            return
        dlg = DependencyGraphDialog(self.rule_editor.toPlainText(), self)
        dlg.exec()

    # ------------------------------------------------------------------
    # Parse Benchmark (7.10.39 initial)
    def _on_benchmark_clicked(self) -> None:
        try:
            from gui.ingestion.parse_benchmark import BenchmarkDialog
        except Exception as e:  # pragma: no cover
            self._append_log(f"Benchmark import failed: {e}")
            return
        # Collect a mapping of filename -> html content for visible (non-hidden) files
        sample_map: dict[str, str] = {}
        max_files = 50  # safeguard
        for it in self._all_file_items:
            if it.isHidden():
                continue
            if len(sample_map) >= max_files:
                break
            data = it.data(0, Qt.ItemDataRole.UserRole)
            if not isinstance(data, dict) or "file" not in data:
                continue
            fpath = data.get("file")
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                    sample_map[fpath] = fh.read()
            except Exception:
                continue
        dlg = BenchmarkDialog(self, sample_files=sample_map)
        dlg.exec()
        self._append_log(
            f"Benchmark run ready with {len(sample_map)} sample files (provide A/B rules in dialog)."
        )

    # ------------------------------------------------------------------
    # Caching Inspector (7.10.40 initial)
    def _on_cache_inspector_clicked(self) -> None:
        try:
            from gui.ingestion.caching_inspector import (
                diff_provenance,
                CachingInspectorDialog,
            )
        except Exception as e:  # pragma: no cover
            self._append_log(f"Caching Inspector import failed: {e}")
            return
        # Build current file hash map (reuse logic from hash impact but avoid changing cached state)
        current_map: dict[str, str] = {}
        for item in self._all_file_items:
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if not isinstance(data, dict) or "file" not in data:
                continue
            fpath = data["file"]
            try:
                with open(fpath, "rb") as fh:
                    import hashlib as _hl

                    current_map[fpath] = _hl.sha1(fh.read()).hexdigest()
            except Exception:
                continue
        prov_map = {p: sha for p, (sha, _ts, _ver) in self._last_provenance.items()}
        diff = diff_provenance(current_map, prov_map)
        dlg = CachingInspectorDialog(diff, self)
        dlg.exec()
        self._append_log("Caching Inspector: " + diff.summary())

    # ------------------------------------------------------------------
    # Security Sandbox Scan (7.10.41)
    def _on_security_scan_clicked(self) -> None:
        try:
            from gui.ingestion.security_sandbox import scan_rules_text
        except Exception as e:  # pragma: no cover
            self._append_log(f"Security sandbox import failed: {e}")
            return
        raw = self.rule_editor.toPlainText()
        report = scan_rules_text(raw)
        if report.ok:
            self._append_log(report.summary())
            return
        # Build textual table of issues
        lines = [report.summary(), "-- Issues --"]
        for i in report.issues[:100]:  # cap to avoid flooding
            loc = f" (line {i.lineno}, col {i.col})" if i.lineno is not None else ""
            field = f" [{i.source}:{i.field}]" if i.field else ""
            lines.append(f"- {i.category}{field}{loc}: {i.message}")
        if len(report.issues) > 100:
            lines.append("(truncated; showing first 100)")
        self._append_log("\n".join(lines))

    # ------------------------------------------------------------------
    # Export / Import (7.10.42)
    def _on_export_rules_clicked(self) -> None:  # pragma: no cover - UI path
        try:
            from gui.ingestion.rule_export import export_rules
        except Exception as e:
            self._append_log(f"Export module import failed: {e}")
            return
        # For simplicity write to fixed file under project root (future: file dialog)
        out_path = os.path.join(self._base_dir, "ingestion_rules_export.json")
        try:
            export_rules(self.rule_editor.toPlainText(), out_path)
        except Exception as e:
            self._append_log(f"Export failed: {e}")
            return
        self._append_log(f"Rules exported -> {out_path}")

    def _on_import_rules_clicked(self) -> None:  # pragma: no cover - UI path
        try:
            from gui.ingestion.rule_export import import_rules
        except Exception as e:
            self._append_log(f"Import module import failed: {e}")
            return
        in_path = os.path.join(self._base_dir, "ingestion_rules_export.json")
        try:
            text = import_rules(in_path)
        except Exception as e:
            self._append_log(f"Import failed: {e}")
            return
        self.rule_editor.setPlainText(text)
        self._append_log(f"Rules imported from {in_path}")

    # ------------------------------------------------------------------
    # Versioning helpers (7.10.33)
    def _on_versions_clicked(self) -> None:
        conn = None
        if _services is not None:
            try:
                conn = _services.try_get("sqlite_conn")
            except Exception:
                conn = None
        if conn is None:
            self._append_log("Versions: no DB connection")
            return
        try:
            from gui.ingestion.rule_versioning import RuleSetVersionStore

            store = RuleSetVersionStore(conn)
            versions = store.list_versions()
            if not versions:
                self._append_log("Versions: none stored")
                return
            self._append_log(
                f"Versions ({len(versions)}): "
                + ", ".join(f"v{v.version_num}" for v in versions[:15])
            )
            if len(versions) > 15:
                self._append_log(f"  ... {len(versions)-15} more")
        except Exception as e:  # pragma: no cover
            self._append_log(f"Versions ERROR: {e}")

    def _on_rollback_clicked(self) -> None:
        conn = None
        if _services is not None:
            try:
                conn = _services.try_get("sqlite_conn")
            except Exception:
                conn = None
        if conn is None:
            self._append_log("Rollback: no DB connection")
            return
        try:
            from gui.ingestion.rule_versioning import RuleSetVersionStore

            store = RuleSetVersionStore(conn)
            prev_json = store.rollback_to_previous()
            if not prev_json:
                self._append_log("Rollback: no previous version")
                return
            self.rule_editor.setPlainText(prev_json)
            self._append_log("Rollback loaded previous version into editor (not applied)")
        except Exception as e:  # pragma: no cover
            self._append_log(f"Rollback ERROR: {e}")

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

    # ------------------------------------------------------------------
    # Theme & Density Integration (7.10.5)
    def _apply_density_and_theme(self) -> None:
        """Apply spacing & palette driven styles.

        Pulls current theme colors & density spacing tokens (if services registered)
        and updates object stylesheet & layout paddings. Reduced color mode sets
        a dynamic widget property consumed by global QSS overrides.
        """
        try:
            from gui.services.service_locator import services as _svc

            theme = _svc.try_get("theme_service")
            density = _svc.try_get("density_service")
            rc_mode = _svc.try_get("reduced_color_mode")
            hc_mode = _svc.try_get(
                "high_contrast_mode"
            )  # optional stub service (bool-ish is_active())
        except Exception:  # pragma: no cover - fallback
            theme = density = rc_mode = hc_mode = None
        # Spacing adjustments
        base_margin = 6
        if density:
            try:
                sp_map = density.spacing()
                base_margin = sp_map.get("md", sp_map.get("base", base_margin))  # type: ignore
            except Exception:
                pass
        lay = self.layout()
        if isinstance(lay, QVBoxLayout):  # type: ignore
            lay.setContentsMargins(base_margin, base_margin, base_margin, base_margin)
            lay.setSpacing(max(4, base_margin - 2))
        # Theme colors
        bg = fg = accent = None
        if theme:
            try:
                colors = theme.colors()  # type: ignore[attr-defined]
                bg = colors.get("background.secondary" or "background.primary")
                fg = colors.get("text.primary")
                accent = colors.get("accent.base")
            except Exception:
                pass
        parts = []
        if bg:
            parts.append(f"#ingestionLabPanel {{ background: {bg}; }}")
        if fg:
            parts.append(
                "#ingestionLabPanel QLabel, #ingestionLabPanel QTreeWidget, #ingestionLabPanel QPlainTextEdit, #ingestionLabPanel QTextEdit { color: %s; }"
                % fg
            )
        if accent:
            parts.append(
                "#ingestionLabPanel QLineEdit { border:1px solid %s; } #ingestionLabPanel QPushButton { border:1px solid %s; }"
                % (accent, accent)
            )
        # Reduced color & high contrast toggle properties
        rc_active = bool(rc_mode and getattr(rc_mode, "is_active", lambda: False)())  # type: ignore
        hc_active = bool(hc_mode and getattr(hc_mode, "is_active", lambda: False)())  # type: ignore
        self.setProperty("reducedColor", "1" if rc_active else "0")
        self.setProperty("highContrast", "1" if hc_active else "0")
        if hc_active:
            # High contrast adaptation: ensure strong backgrounds & clear borders for dense text panes
            parts.append(
                "#ingestionLabPanel QTextEdit#ingestionLabPreview, "
                "#ingestionLabPanel QPlainTextEdit#ingestionLabLog, "
                "#ingestionLabPanel QPlainTextEdit#ingestionLabRuleEditor { "
                "background:#000000; color:#FFFFFF; selection-background-color:#FFFFFF; selection-color:#000000; }"
            )
        if rc_active:
            # Reduced color mode: remove potentially confusing accent borders inside panel core areas
            parts.append(
                "#ingestionLabPanel QTreeWidget, #ingestionLabPanel QTextEdit, #ingestionLabPanel QPlainTextEdit {"
                " border-color: #666; }"
            )
        if parts:
            # Append specific editor/log/preview styling derived from theme tokens when present.
            if theme and fg and bg:
                # Derive secondary surfaces (fallbacks if missing)
                try:
                    colors = theme.colors()  # type: ignore[attr-defined]
                except Exception:
                    colors = {}
                surf = colors.get("surface.card", colors.get("background.secondary", bg))
                editor_bg = colors.get("background.editor", surf)
                log_bg = colors.get("background.console", surf)
                prev_bg = colors.get("background.preview", surf)
                border_col = colors.get("border.medium", colors.get("accent.base", fg))
                mono = "Consolas,'Courier New',monospace"
                parts.append(
                    f"QPlainTextEdit#ingestionLabRuleEditor {{ background:{editor_bg}; color:{fg}; border:1px solid {border_col}; font-family:{mono}; font-size:12px; }}"
                )
                parts.append(
                    f"QPlainTextEdit#ingestionLabLog {{ background:{log_bg}; color:{fg}; border:1px solid {border_col}; font-family:{mono}; font-size:12px; }}"
                )
                parts.append(
                    f"QTextEdit#ingestionLabPreview {{ background:{prev_bg}; color:{fg}; border:1px solid {border_col}; font-family:{mono}; font-size:12px; }}"
                )
            self.setStyleSheet("\n".join(parts))

    # ------------------------------------------------------------------
    # Performance badge helpers (7.10.45)
    def _now(self) -> float:  # separated for test injection
        return time.perf_counter()

    def _update_performance_badge(self, elapsed_ms: float) -> None:
        """Show or hide preview performance badge based on threshold.

        Parameters
        ----------
        elapsed_ms: float
            Measured preview duration in milliseconds.
        """
        thresh = self.preview_perf_threshold_ms
        # Guard: elapsed_ms may be tiny in fast CI; rely on env override in tests
        if elapsed_ms > thresh:
            self._perf_badge.setText(f"Preview {elapsed_ms:.1f}ms (> {thresh:.0f}ms threshold)")
            self._perf_badge.setVisible(True)
            self._perf_badge_active = True
        else:
            self._perf_badge.setVisible(False)
            self._perf_badge_active = False

    def on_theme_changed(self, theme, changed_keys):  # type: ignore[override]
        # Re-apply full styling (cheap) on any theme change
        try:
            self._apply_density_and_theme()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Filtering logic (7.10.4)
    def _apply_filters(self) -> None:
        """Apply in-memory filters to existing tree items without re-scanning disk.

        Filters:
          - Search text (substring, case-insensitive) over relative filename & hash column.
          - Phase inclusion checkboxes.
          - Size range (KB) minimum / maximum (0 means no bound for max; min always enforced).
          - Modified within last N hours (0 = any). Uses os.stat; best-effort.
        Phase parent visibility auto-updates based on whether any children remain visible.
        """
        if not self._all_file_items:
            return
        text = (self.search_box.text() or "").lower()
        min_kb = self.min_size.value()
        max_kb = self.max_size.value() or None
        hours = self.modified_within_hours.value()
        allowed_phases = {pid for pid, cb in self._phase_checks.items() if cb.isChecked()}
        now = None
        if hours:
            import time as _t

            now = _t.time()
        # Track parents needing visibility recompute
        parents = []  # collect unique parent items preserving insertion order
        for item in self._all_file_items:
            data = item.data(0, Qt.ItemDataRole.UserRole) or {}
            phase = data.get("phase") if isinstance(data, dict) else None
            rel = item.text(1)
            hash_short = item.text(3)
            size_txt = item.text(2)
            visible = True
            # Phase filter
            if phase and phase not in allowed_phases:
                visible = False
            # Search filter
            if visible and text:
                hay = f"{rel.lower()} {hash_short.lower()}"
                if text not in hay:
                    visible = False
            # Size filter
            if visible:
                try:
                    size_val = float(size_txt) if size_txt and size_txt != "?" else 0.0
                except Exception:
                    size_val = 0.0
                if size_val < min_kb:
                    visible = False
                if max_kb is not None and max_kb > 0 and size_val > max_kb:
                    visible = False
            # Modified within filter
            if visible and hours and rel:
                # reconstruct absolute path
                abs_path = os.path.join(self._base_dir, rel)
                try:
                    st = os.stat(abs_path)
                    if now and (now - st.st_mtime) > hours * 3600:
                        visible = False
                except Exception:
                    pass
            item.setHidden(not visible)
            parent = item.parent()
            if parent and parent not in parents:
                parents.append(parent)
        # Update parent (phase) node visibility
        for p in parents:
            child_visible = any(not p.child(i).isHidden() for i in range(p.childCount()))
            p.setHidden(not child_visible)

    # For tests
    def filtered_file_count(self) -> int:
        return sum(1 for it in self._all_file_items if not it.isHidden())

    # ------------------------------------------------------------------
    # Draft autosave & publish (7.10.49)
    def _on_rule_text_changed(self) -> None:  # pragma: no cover - GUI event
        # Mark draft dirty; actual write deferred to timer based autosave
        self._draft_dirty = True

    def _autosave_draft(self) -> None:
        """Persist current editor text to the draft file if dirty.

        Uses an atomic write pattern (temp file + replace) to avoid partial writes.
        Silent on errors (but logs a warning) — autosave should never raise.
        """
        if not self._draft_dirty:
            return
        text = self.rule_editor.toPlainText()
        # Do not save empty drafts (avoid overwriting an existing draft with blank)
        if not (text and text.strip()):
            return
        try:
            tmp_path = self._draft_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8", errors="ignore") as fh:
                json.dump({"text": text, "ts": int(time.time())}, fh, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self._draft_path)
            self._draft_dirty = False
            # Provide lightweight feedback (single line; throttled by dirty flag)
            self._append_log("Draft autosaved")
        except Exception as e:  # pragma: no cover - best effort
            try:
                self._append_log(f"Draft autosave WARN: {e}")
            except Exception:
                pass

    def _load_existing_draft(self) -> None:
        """Load existing draft file into editor if editor currently empty.

        This ensures that interrupted sessions restore work-in-progress content
        without clobbering any pre-populated editor text (e.g., when loading a
        previous version or template before instantiation of autosave system).
        """
        if not os.path.exists(self._draft_path):
            return
        current = self.rule_editor.toPlainText()
        if current.strip():  # User already has content; do not overwrite implicitly
            return
        try:
            with open(self._draft_path, "r", encoding="utf-8", errors="ignore") as fh:
                payload = json.load(fh)
            if isinstance(payload, dict) and isinstance(payload.get("text"), str):
                self.rule_editor.setPlainText(payload.get("text", ""))
                self._draft_dirty = False
                self._append_log("Draft restored")
        except Exception as e:  # pragma: no cover
            self._append_log(f"Draft restore WARN: {e}")

    def _on_publish_clicked(self) -> None:
        """Publish current draft: save as formal version (if changed) & clear draft state."""
        raw = (self.rule_editor.toPlainText() or "").strip()
        if not raw:
            self._append_log("Publish: editor empty")
            return
        # Compute content hash to detect no-op publishes
        try:
            content_hash = hashlib.sha1(raw.encode("utf-8", "ignore")).hexdigest()
        except Exception as e:  # pragma: no cover
            self._append_log(f"Publish ERROR (hash): {e}")
            return
        if content_hash == self._last_published_hash:
            self._append_log("Publish: no changes since last publish")
            return
        # Attempt structured parse to validate before publish
        try:
            js = json.loads(raw) if raw else {}
            if not isinstance(js, dict):
                raise ValueError("Root must be a JSON object")
        except Exception as e:
            self._append_log(f"Publish ERROR (parse): {e}")
            return
        # Store as version if version store available
        conn = None
        if _services is not None:
            try:
                conn = _services.try_get("sqlite_conn")
            except Exception:
                conn = None
        version_num = None
        if conn is not None:
            try:
                from gui.ingestion.rule_versioning import RuleSetVersionStore

                store = RuleSetVersionStore(conn)
                version_num = store.save_version(js, raw)
            except Exception as e:  # pragma: no cover
                self._append_log(f"Publish WARN (version store): {e}")
        self._last_published_hash = content_hash
        # Remove draft file (best effort)
        try:
            if os.path.exists(self._draft_path):
                os.remove(self._draft_path)
        except Exception:  # pragma: no cover
            pass
        self._draft_dirty = False
        msg = f"Published draft (hash={content_hash[:10]})"
        if version_num is not None:
            msg += f" -> v{version_num}"
            self._last_version_num = version_num
        self._append_log(msg)
        # Emit publish event (optional, mirrors apply event pattern)
        if _services is not None:
            try:
                from gui.services.event_bus import GUIEvent, EventBus  # local import

                bus: "EventBus" | None = _services.try_get("event_bus")  # type: ignore[name-defined]
                if bus:
                    bus.publish(
                        GUIEvent.INGEST_RULES_PUBLISHED,
                        {"hash": content_hash, "version": version_num},
                    )
            except Exception:  # pragma: no cover
                pass
