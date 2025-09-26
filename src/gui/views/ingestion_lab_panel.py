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
)
from PyQt6.QtCore import Qt
import json
from gui.components.theme_aware import ThemeAwareMixin
import sqlite3
import hashlib
from dataclasses import dataclass
from typing import Dict, Any

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
        self.btn_simulate.setToolTip("Run safe simulation (adapter + coverage + gates) — no DB writes")
        self.btn_apply = QPushButton("Apply")
        self.btn_apply.setToolTip("Apply last successful simulation (audit only in this milestone)")
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
        self.btn_hash_impact.clicked.connect(self._on_hash_impact_clicked)  # type: ignore
        self.btn_field_coverage.clicked.connect(self._on_field_coverage_clicked)  # type: ignore
        self.btn_orphan_fields.clicked.connect(self._on_orphan_fields_clicked)  # type: ignore
        self.btn_quality_gates.clicked.connect(self._on_quality_gates_clicked)  # type: ignore
        self.btn_simulate.clicked.connect(self._on_simulate_clicked)  # type: ignore
        self.btn_apply.clicked.connect(self._on_apply_clicked)  # type: ignore
        self.search_box.textChanged.connect(lambda _t: self._apply_filters())  # type: ignore
        self.min_size.valueChanged.connect(lambda _v: self._apply_filters())  # type: ignore
        self.max_size.valueChanged.connect(lambda _v: self._apply_filters())  # type: ignore
        self.modified_within_hours.valueChanged.connect(lambda _v: self._apply_filters())  # type: ignore

        # Internal cache of all file items for filtering without re-scanning
        # Holds all leaf file items for filtering purposes
        self._all_file_items = []  # type: list[QTreeWidgetItem]
        # Cache last field coverage report for tests (Milestone 7.10.26)
        self._last_field_coverage = None  # type: ignore[assignment]
        # Safe apply guard state (7.10.30/31)
        try:
            self._safe_guard = SafeApplyGuard()
        except Exception:  # pragma: no cover
            self._safe_guard = None
        self._last_simulation_id: int | None = None
        # Inline banner label for post-apply summary (7.10.31)
        self._banner = QLabel("")
        self._banner.setObjectName("ingestionLabBanner")
        self._banner.setStyleSheet(
            "#ingestionLabBanner { border:1px solid #888; padding:4px; border-radius:4px; background: rgba(200,200,200,0.15); }"
        )
        self._banner.setVisible(False)
        root.insertWidget(0, self._banner)
        self._last_apply_summary: dict[str, any] = {}

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
            # Retrieve provenance metadata we stashed in column 2 user role
            prov_payload = target.data(2, Qt.ItemDataRole.UserRole) or {}
            if isinstance(prov_payload, dict):
                hash_full = prov_payload.get("hash")
                last_ingested = prov_payload.get("last_ingested_at")
                parser_ver = prov_payload.get("parser_version")
            else:  # pragma: no cover - defensive
                hash_full = last_ingested = parser_ver = None
            meta = [
                f"File: {fpath}",
                f"Size: {stat.st_size} bytes",  # raw bytes
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
        # Build summary (unchanged/skipped placeholders for now)
        inserted_total = sum(result.rows_by_resource.values())
        summary_text = (
            f"Apply Summary sim={result.sim_id} inserted_rows={inserted_total} resources={len(result.rows_by_resource)}"
        )
        self._banner.setText(summary_text)
        self._banner.setVisible(True)
        self._last_apply_summary = {
            "sim_id": result.sim_id,
            "inserted_total": inserted_total,
            "rows_by_resource": dict(result.rows_by_resource),
        }
        self._append_log(summary_text)

    # Snapshot for tests
    def apply_summary_snapshot(self) -> Dict[str, Any]:  # pragma: no cover - test helper
        return dict(self._last_apply_summary)

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
        except Exception:  # pragma: no cover - fallback
            theme = density = rc_mode = None
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
        # Reduced color toggle property
        if rc_mode and getattr(rc_mode, "is_active", lambda: False)():  # type: ignore
            self.setProperty("reducedColor", "1")
        else:
            self.setProperty("reducedColor", "0")
        if parts:
            self.setStyleSheet("\n".join(parts))

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
