"""Main ingestion lab panel implementation assembled from feature mixins."""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QCheckBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStackedLayout,
    QTabWidget,
    QTextEdit,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gui.components.theme_aware import ThemeAwareMixin
from gui.ingestion.rule_intent_store import RuleIntentStore
from gui.ingestion.selector_watchlist_store import (
    SelectorWatchResult,
    SelectorWatchlistStore,
)
from gui.views.rule_intent_sidebar import RuleIntentSidebar
from gui.views.selector_watchlist_panel import SelectorWatchlistPanel

from .analysis import AnalysisMixin
from .constants import OTHER_PHASE_ID, PHASE_PATTERNS
from .drafts import DraftingMixin
from .file_discovery import FileDiscoveryMixin
from .filters import FilteringMixin
from .hash_impact import HashImpactResult
from .intent_sidebar import IntentSidebarMixin
from .preview import PreviewMixin
from .prompt import PromptAssistMixin
from .sandbox import SandboxMixin
from .simulation import SimulationMixin
from .tools import ToolDialogsMixin
from .watchlist import WatchlistMixin

try:  # pragma: no cover - optional import
    from gui.components.skeleton_loader import SkeletonLoaderWidget
except Exception:  # pragma: no cover
    SkeletonLoaderWidget = None  # type: ignore

try:  # pragma: no cover - optional apply guard import
    from gui.ingestion.rule_apply_guard import SafeApplyGuard
except Exception:  # pragma: no cover
    SafeApplyGuard = None  # type: ignore

try:  # pragma: no cover - import guard
    from gui.services.service_locator import services as _services  # type: ignore
except Exception:  # pragma: no cover
    _services = None  # type: ignore

__all__ = ["IngestionLabPanel", "HashImpactResult"]


class IngestionLabPanel(
    QWidget,
    ThemeAwareMixin,
    WatchlistMixin,
    IntentSidebarMixin,
    AnalysisMixin,
    SimulationMixin,
    ToolDialogsMixin,
    DraftingMixin,
    SandboxMixin,
    FilteringMixin,
    FileDiscoveryMixin,
    PreviewMixin,
    PromptAssistMixin,
):
    """Dockable panel container for the Ingestion Lab."""

    def __init__(self, base_dir: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("ingestionLabPanel")
        self._base_dir = base_dir
        self._intent_store_path = os.path.join(self._base_dir, ".ingestion_rule_intents.json")
        self._intent_store = RuleIntentStore(self._intent_store_path)
        self._intent_current_resource: Optional[str] = None
        self._watchlist_store_path = os.path.join(
            self._base_dir, ".ingestion_selector_watchlist.json"
        )
        self._watchlist_store = SelectorWatchlistStore(self._watchlist_store_path)
        self._last_watchlist_results: Dict[str, SelectorWatchResult] = {}
        self._current_ruleset = None
        self._base_inglab_stylesheet = self.styleSheet()
        self._build_ui()
        self._watchlist_panel.set_entries(self._watchlist_store.entries())
        self._last_provenance: Dict[str, tuple[str, str, int]] = {}
        self._last_hash_impact: HashImpactResult | None = None
        self.refresh_file_list()
        try:
            self._apply_density_and_theme()
        except Exception:
            pass

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        self._action_container = QWidget()
        self._action_container.setObjectName("ingLabToolbarContainer")
        toolbar_v = QVBoxLayout(self._action_container)
        toolbar_v.setContentsMargins(0, 0, 0, 0)
        toolbar_v.setSpacing(2)

        actions = QHBoxLayout()
        actions.setContentsMargins(4, 4, 4, 4)
        actions.setSpacing(4)
        self._actions_layout = actions
        self._button_text_cache: dict[QAbstractButton, str] = {}
        self._icon_buttons: list[QAbstractButton] = []
        self._toolbutton_style_cache: dict[QToolButton, Qt.ToolButtonStyle] = {}

        self._toolbar_row2 = QHBoxLayout()
        self._toolbar_row2.setContentsMargins(4, 0, 4, 4)
        self._toolbar_row2.setSpacing(4)

        self._toolbar_row2_widget = QWidget()
        self._toolbar_row2_widget.setLayout(self._toolbar_row2)
        self._toolbar_row2_widget.setVisible(False)

        toolbar_v.addLayout(actions)
        toolbar_v.addWidget(self._toolbar_row2_widget)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setObjectName("ingLabBtnRefresh")
        self.btn_preview = QPushButton("Preview")
        self.btn_preview.setObjectName("ingLabBtnPreview")
        self.btn_preview.setEnabled(False)
        self.btn_example_rows = QPushButton("Example Rows")
        self.btn_example_rows.setObjectName("ingLabBtnExampleRows")
        self.btn_example_rows.setToolTip(
            "Generate synthetic example rows that illustrate transform outcomes."
        )
        self.btn_watchlist = QPushButton("Watchlist")
        self.btn_watchlist.setObjectName("ingLabBtnWatchlist")
        self.btn_watchlist.setToolTip(
            "Run the selector drift watchlist and open the monitoring panel."
        )
        self.btn_hash_impact = QPushButton("Hash Impact")
        self.btn_hash_impact.setObjectName("ingLabBtnHashImpact")
        self.btn_hash_impact.setToolTip("Compute which files would trigger ingest (hash changes)")
        self.btn_field_coverage = QPushButton("Field Coverage")
        self.btn_field_coverage.setObjectName("ingLabBtnFieldCoverage")
        self.btn_field_coverage.setToolTip(
            "Compute per-field non-empty ratios across all visible files using current rules"
        )
        self.btn_field_coverage_radar = QPushButton("Coverage Radar")
        self.btn_field_coverage_radar.setObjectName("ingLabBtnFieldCoverageRadar")
        self.btn_field_coverage_radar.setToolTip(
            "Show radar chart of semantic field category coverage (identity/performance/schedule/meta)"
        )
        self.btn_orphan_fields = QPushButton("Orphan Fields")
        self.btn_orphan_fields.setObjectName("ingLabBtnOrphanFields")
        self.btn_orphan_fields.setToolTip("List extracted fields lacking mapping entries")
        self.btn_quality_gates = QPushButton("Quality Gates")
        self.btn_quality_gates.setObjectName("ingLabBtnQualityGates")
        self.btn_quality_gates.setToolTip(
            "Evaluate minimum non-null ratios (quality gate config under 'quality_gates' in rules JSON)"
        )
        self.btn_overlap = QPushButton("Conflicts")
        self.btn_overlap.setObjectName("ingLabBtnOverlap")
        self.btn_overlap.setToolTip(
            "Detect overlapping selectors among resources (potential redundancy/conflicts)."
        )
        self.btn_simulate = QPushButton("Simulate")
        self.btn_simulate.setObjectName("ingLabBtnSimulate")
        self.btn_simulate.setToolTip(
            "Run safe simulation (adapter + coverage + gates) — no DB writes"
        )
        self.btn_apply = QPushButton("Apply")
        self.btn_apply.setObjectName("ingLabBtnApply")
        self.btn_apply.setToolTip("Apply last successful simulation (audit only in this milestone)")
        self.btn_versions = QPushButton("Versions")
        self.btn_versions.setObjectName("ingLabBtnVersions")
        self.btn_versions.setToolTip("List stored rule set versions in log")
        self.btn_rollback = QPushButton("Rollback")
        self.btn_rollback.setObjectName("ingLabBtnRollback")
        self.btn_rollback.setToolTip("Load previous rule version into editor (not yet applied)")
        self.btn_export = QPushButton("Export")
        self.btn_export.setObjectName("ingLabBtnExport")
        self.btn_export.setToolTip("Export current rules to a JSON file")
        self.btn_import = QPushButton("Import")
        self.btn_import.setObjectName("ingLabBtnImport")
        self.btn_import.setToolTip("Import rules from a JSON file (replaces editor contents)")
        self.btn_selector_picker = QPushButton("Pick Selector")
        self.btn_selector_picker.setObjectName("ingLabBtnSelectorPicker")
        self.btn_selector_picker.setToolTip(
            "Open visual picker to build CSS selector from sample HTML"
        )
        self.btn_regex_tester = QPushButton("Regex Tester")
        self.btn_regex_tester.setObjectName("ingLabBtnRegexTester")
        self.btn_regex_tester.setToolTip("Open regex tester dialog for pattern experimentation")
        self.btn_derived = QPushButton("Derived Fields")
        self.btn_derived.setObjectName("ingLabBtnDerived")
        self.btn_derived.setToolTip(
            "Compose derived fields (expressions referencing existing extracted fields)"
        )
        self.btn_dep_graph = QPushButton("Dep Graph")
        self.btn_dep_graph.setObjectName("ingLabBtnDepGraph")
        self.btn_dep_graph.setToolTip("Show dependency graph (base + derived field relationships)")
        self.btn_bulk_edit = QPushButton("Bulk Edit")
        self.btn_bulk_edit.setObjectName("ingLabBtnBulkEdit")
        self.btn_bulk_edit.setToolTip(
            "Open multi-select bulk edit dialog to apply transforms or selector refinement across fields"
        )
        self.btn_benchmark = QPushButton("Benchmark")
        self.btn_benchmark.setObjectName("ingLabBtnBenchmark")
        self.btn_benchmark.setToolTip(
            "Run A/B parse benchmark comparing two rule variants over a sample of visible files"
        )
        self.btn_cache = QPushButton("Cache Inspect")
        self.btn_cache.setObjectName("ingLabBtnCache")
        self.btn_cache.setToolTip(
            "Show which files are unchanged (cache hit) vs updated/new/missing based on provenance"
        )
        self.btn_security = QPushButton("Security Scan")
        self.btn_security.setObjectName("ingLabBtnSecurity")
        self.btn_security.setToolTip(
            "Run static security sandbox scan over expression & derived transforms"
        )
        self.btn_visual_builder = QPushButton("Visual Builder")
        self.btn_visual_builder.setObjectName("ingLabBtnVisualBuilder")
        self.btn_visual_builder.setToolTip(
            "Open visual rule builder canvas (drag/drop authoring scaffold)"
        )
        self.btn_prompt_assist = QPushButton("Prompt Assist")
        self.btn_prompt_assist.setObjectName("ingLabBtnPromptAssist")
        self.btn_prompt_assist.setToolTip(
            "Generate draft rules from a natural language description (heuristic)."
        )
        self.btn_publish = QPushButton("Publish")
        self.btn_publish.setObjectName("ingLabBtnPublish")
        self.btn_publish.setToolTip(
            "Persist current draft rule set as the active published version (creates new version entry if changed)."
        )
        try:
            self.btn_prompt_assist.clicked.connect(self._on_prompt_assist)  # type: ignore
        except Exception:
            pass

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search filename or hash…")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.setObjectName("ingestionLabSearch")

        self.phase_filter_button = QToolButton()
        self.phase_filter_button.setText("Phases ▾")
        self.phase_filter_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._phase_menu = QMenu(self)
        self._phase_checks = {}
        for pid, label, _ in PHASE_PATTERNS + [(OTHER_PHASE_ID, "Other", lambda *_: False)]:
            cb = QCheckBox(label)
            cb.setChecked(True)
            act = self._phase_menu.addAction(label)

            def _toggle(_checked: bool = False, box=cb):
                box.setChecked(not box.isChecked())
                self._apply_filters()

            act.triggered.connect(_toggle)  # type: ignore
            self._phase_checks[pid] = cb
        self.phase_filter_button.setMenu(self._phase_menu)

        self.min_size = QSpinBox()
        self.min_size.setPrefix(">= ")
        self.min_size.setMaximum(10_000)
        self.min_size.setToolTip("Minimum size (KB)")
        self.max_size = QSpinBox()
        self.max_size.setPrefix("<= ")
        self.max_size.setMaximum(10_000)
        self.max_size.setToolTip("Maximum size (KB; 0 = no limit)")
        self.modified_within_hours = QSpinBox()
        self.modified_within_hours.setPrefix("< ")
        self.modified_within_hours.setMaximum(720)
        self.modified_within_hours.setToolTip("Show files modified within last N hours (0 = any)")

        def _make_cat_panel(title: str, buttons: list[QWidget]) -> QWidget:
            wrapper = QWidget()
            wrapper.setObjectName("ingLabCatPanel")
            vlay = QVBoxLayout(wrapper)
            vlay.setContentsMargins(6, 4, 6, 6)
            vlay.setSpacing(4)
            lab = QLabel(title)
            lab.setObjectName("ingLabGroupLabel")
            lab.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
            vlay.addWidget(lab)
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(4)
            for b in buttons:
                row.addWidget(b)
            row.addStretch(1)
            vlay.addLayout(row)
            return wrapper

        core_panel = _make_cat_panel(
            "Core",
            [
                self.btn_refresh,
                self.btn_preview,
                self.btn_simulate,
                self.btn_apply,
                self.btn_publish,
            ],
        )
        authoring_panel = _make_cat_panel(
            "Authoring",
            [
                self.btn_selector_picker,
                self.btn_regex_tester,
                self.btn_prompt_assist,
                self.btn_visual_builder,
                self.btn_bulk_edit,
                self.btn_derived,
                self.btn_dep_graph,
            ],
        )
        analysis_panel = _make_cat_panel(
            "Analysis",
            [
                self.btn_field_coverage,
                self.btn_field_coverage_radar,
                self.btn_example_rows,
                self.btn_watchlist,
                self.btn_quality_gates,
                self.btn_orphan_fields,
                self.btn_overlap,
            ],
        )

        self.sandbox_input = QPlainTextEdit()
        self.sandbox_input.setObjectName("ingestionLabSandboxFragment")
        self.sandbox_input.setPlaceholderText(
            "Paste or type a small HTML fragment here (e.g. a snippet containing a table or list)."
        )
        try:
            from gui.services.service_locator import services as _svc

            if not _svc.try_get("theme_service"):
                self.sandbox_input.setStyleSheet(
                    "QPlainTextEdit#ingestionLabSandboxFragment { background:#101010; color:#e8e8e8; font-family:Consolas,'Courier New',monospace; font-size:12px; }"
                )
        except Exception:
            self.sandbox_input.setStyleSheet(
                "QPlainTextEdit#ingestionLabSandboxFragment { background:#101010; color:#e8e8e8; font-family:Consolas,'Courier New',monospace; font-size:12px; }"
            )

        self.sandbox_output = QPlainTextEdit()
        self.sandbox_output.setObjectName("ingestionLabSandboxOutput")
        self.sandbox_output.setReadOnly(True)
        self.sandbox_output.setPlaceholderText("Sandbox parse results will appear here.")
        try:
            if not _svc.try_get("theme_service"):
                self.sandbox_output.setStyleSheet(
                    "QPlainTextEdit#ingestionLabSandboxOutput { background:#080808; color:#dcdcdc; font-family:Consolas,'Courier New',monospace; font-size:12px; }"
                )
        except Exception:
            self.sandbox_output.setStyleSheet(
                "QPlainTextEdit#ingestionLabSandboxOutput { background:#080808; color:#dcdcdc; font-family:Consolas,'Courier New',monospace; font-size:12px; }"
            )

        self.btn_sandbox_parse = QPushButton("Parse")
        self.btn_sandbox_parse.setObjectName("ingLabBtnSandboxParse")
        self.btn_sandbox_parse.setToolTip(
            "Parse fragment with current rules (no transforms unless enabled)"
        )
        self.btn_sandbox_clear = QPushButton("Clear")
        self.btn_sandbox_clear.setObjectName("ingLabBtnSandboxClear")
        self.btn_sandbox_clear.setToolTip("Clear fragment and output")
        self.chk_sandbox_transforms = QCheckBox("Apply transforms")
        self.chk_sandbox_transforms.setObjectName("ingLabChkSandboxTransforms")
        self.chk_sandbox_transforms.setToolTip(
            "If checked, run transform chains for list field values"
        )
        self._sandbox_tab = QWidget()
        self._sandbox_tab.setObjectName("ingLabSandboxTab")
        sandbox_layout = QVBoxLayout(self._sandbox_tab)
        sandbox_layout.setContentsMargins(8, 6, 8, 8)
        sandbox_layout.setSpacing(6)

        sandbox_actions = QHBoxLayout()
        sandbox_actions.setContentsMargins(0, 0, 0, 0)
        sandbox_actions.setSpacing(6)
        sandbox_actions.addWidget(self.btn_sandbox_parse)
        sandbox_actions.addWidget(self.btn_sandbox_clear)
        sandbox_actions.addWidget(self.chk_sandbox_transforms)
        sandbox_actions.addStretch(1)
        sandbox_layout.addLayout(sandbox_actions)

        self._sandbox_split = QSplitter(Qt.Orientation.Vertical, self._sandbox_tab)
        self._sandbox_split.setChildrenCollapsible(False)
        self.sandbox_input.setParent(self._sandbox_split)
        self.sandbox_output.setParent(self._sandbox_split)
        self._sandbox_split.addWidget(self.sandbox_input)
        self._sandbox_split.addWidget(self.sandbox_output)
        self._sandbox_split.setStretchFactor(0, 3)
        self._sandbox_split.setStretchFactor(1, 2)
        sandbox_layout.addWidget(self._sandbox_split)

        self._advanced_buttons = [
            self.btn_hash_impact,
            self.btn_versions,
            self.btn_rollback,
            self.btn_export,
            self.btn_import,
            self.btn_benchmark,
            self.btn_cache,
            self.btn_security,
        ]
        for _btn in self._advanced_buttons:
            _btn.setParent(self)
            _btn.setVisible(False)

        actions.addWidget(core_panel)
        actions.addWidget(authoring_panel)
        actions.addWidget(analysis_panel)

        self.btn_advanced_menu = QToolButton()
        self.btn_advanced_menu.setText("Advanced")
        self.btn_advanced_menu.setObjectName("ingLabBtnAdvancedMenu")
        self.btn_advanced_menu.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_advanced_menu.setToolTip("Advanced utilities and export actions")
        self._advanced_menu = QMenu(self.btn_advanced_menu)
        for button in self._advanced_buttons:
            act = self._advanced_menu.addAction(button.text())
            act.triggered.connect(button.click)  # type: ignore
        self.btn_advanced_menu.setMenu(self._advanced_menu)
        actions.addWidget(self.btn_advanced_menu)

        self._analysis_panel = analysis_panel

        try:
            import os as _os_temp

            if not _os_temp.environ.get("RP_TEST_MODE") and not getattr(
                self, "_applied_streamlined_style", False
            ):
                self._applied_streamlined_style = True
                self.setStyleSheet(
                    self.styleSheet()
                    + "\n"
                    + """
                    QLabel#ingLabGroupLabel {\n  padding: 2px 6px;\n  font-weight: bold;\n  color: rgb(155,188,223);\n  background: rgba(90,160,220,0.08);\n  border-radius: 4px;\n}\n
                    QPushButton, QToolButton {\n  padding: 4px 6px;\n  border: 1px solid rgba(255,255,255,0.07);\n  background: rgba(255,255,255,0.04);\n  border-radius: 4px;\n}\n
                    QPushButton:hover, QToolButton:hover {\n  background: rgba(120,180,255,0.18);\n  border-color: rgba(140,200,255,0.35);\n}\n
                    QPushButton:pressed, QToolButton:pressed {\n  background: rgba(120,180,255,0.30);\n}\n
                    QToolButton#ingLabBtnAdvancedMenu {\n  font-weight: bold;\n}\n                    """
                )
        except Exception:
            pass

        self._filters_widget = QWidget()
        filters_layout = QHBoxLayout(self._filters_widget)
        filters_layout.setContentsMargins(0, 0, 0, 0)
        filters_layout.setSpacing(4)
        self.search_box.setMaximumWidth(460)
        try:
            if not os.environ.get("RP_TEST_MODE"):
                self.search_box.setStyleSheet(
                    "QLineEdit#ingestionLabSearch { background: rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.12); padding:4px 6px; border-radius:4px; color:#e6e6e6; }"
                    "QLineEdit#ingestionLabSearch:focus { border-color: rgba(120,180,255,0.55); background: rgba(255,255,255,0.10); }"
                )
        except Exception:
            pass
        filters_layout.addWidget(self.search_box)
        filters_layout.addWidget(self.phase_filter_button)
        filters_layout.addWidget(QLabel("Size KB:"))
        filters_layout.addWidget(self.min_size)
        filters_layout.addWidget(self.max_size)
        filters_layout.addWidget(QLabel("Mod <h:"))
        filters_layout.addWidget(self.modified_within_hours)

        actions.addStretch(1)
        self.btn_toggle_filters = QToolButton()
        self.btn_toggle_filters.setText("Filters")
        self.btn_toggle_filters.setCheckable(True)
        self.btn_toggle_filters.setChecked(True)
        self.btn_toggle_filters.setObjectName("ingLabBtnToggleFilters")
        self.btn_toggle_filters.setToolTip(
            "Show / hide filter inputs (search, phase, size, modified)"
        )
        actions.addWidget(self.btn_toggle_filters)
        actions.addWidget(self._filters_widget)
        actions.addStretch(2)

        def _toggle_filters() -> None:
            vis = self.btn_toggle_filters.isChecked()
            self._filters_widget.setVisible(vis)
            try:
                s = QSettings("RosterPlanner", "IngestionLab")
                s.setValue("filters_visible", bool(vis))
            except Exception:
                pass

        self.btn_toggle_filters.toggled.connect(_toggle_filters)  # type: ignore
        try:
            s = QSettings("RosterPlanner", "IngestionLab")
            val = s.value("filters_visible", True, type=bool)
            self.btn_toggle_filters.setChecked(bool(val))
            _toggle_filters()
        except Exception:
            pass

        scroll_bar = QScrollArea()
        scroll_bar.setWidgetResizable(True)
        scroll_bar.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_bar.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_bar.setWidget(self._action_container)
        scroll_bar.setViewportMargins(0, 0, 0, -4)
        root.addWidget(scroll_bar)

        self.btn_toggle_density = QToolButton()
        self.btn_toggle_density.setText("Compact")
        self.btn_toggle_density.setCheckable(True)
        self.btn_toggle_density.setToolTip("Toggle compact density for action bar buttons")
        actions.insertWidget(0, self.btn_toggle_density)

        def _handle_density_toggle(state: bool) -> None:
            self._on_density_toggled(state)

        self.btn_toggle_density.toggled.connect(_handle_density_toggle)  # type: ignore
        try:
            s = QSettings("RosterPlanner", "IngestionLab")
            dens = s.value("compact_density", False, type=bool)
            self.btn_toggle_density.setChecked(bool(dens))
        except Exception:
            pass
        self._on_density_toggled(self.btn_toggle_density.isChecked(), persist=False)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        root.addWidget(splitter, 1)

        self.file_tree = QTreeWidget()
        self.file_tree.setObjectName("ingestionLabFileTree")
        try:
            self.file_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        except Exception:
            pass
        self.file_tree.setHeaderLabels(
            ["Phase", "File", "Size (KB)", "Hash", "Last Ingested", "Parser Ver"]
        )
        self.file_tree.setColumnWidth(0, 140)
        self.file_tree.setColumnWidth(2, 70)
        self.file_tree.setColumnWidth(3, 110)
        self.file_tree.setColumnWidth(4, 120)
        self.file_tree.setColumnWidth(5, 70)
        self.file_list = self.file_tree  # legacy alias
        self.file_tree.itemSelectionChanged.connect(self._on_file_selection_changed)  # type: ignore
        splitter.addWidget(self.file_tree)

        mid_split = QSplitter(Qt.Orientation.Vertical, self)
        splitter.addWidget(mid_split)

        self._editor_stack_container = QWidget()
        self._editor_stack = QStackedLayout(self._editor_stack_container)
        self.rule_editor = QPlainTextEdit()
        self.rule_editor.setObjectName("ingestionLabRuleEditor")
        self.rule_editor.setPlaceholderText(
            "# Define extraction rules here (YAML or JSON)\n# e.g.\n# ranking_table:\n#   selector: 'table.ranking'\n#   columns: [team, points, diff]\n"
        )
        try:
            from gui.services.service_locator import services as _svc

            if not _svc.try_get("theme_service"):
                self.rule_editor.setStyleSheet(
                    "QPlainTextEdit#ingestionLabRuleEditor { background:#1b1b1b; color:#f0f0f0; font-family:Consolas,'Courier New',monospace; font-size:12px; }"
                )
        except Exception:
            self.rule_editor.setStyleSheet(
                "QPlainTextEdit#ingestionLabRuleEditor { background:#1b1b1b; color:#f0f0f0; font-family:Consolas,'Courier New',monospace; font-size:12px; }"
            )
        self._editor_stack.addWidget(self.rule_editor)
        try:
            from gui.ingestion.visual_rule_builder import VisualRuleBuilder  # type: ignore

            vb = VisualRuleBuilder()
            if getattr(vb, "_last_error", None):
                msg = getattr(vb, "_last_error")
                self.visual_builder = QLabel(f"Visual builder unavailable: {msg}")
            else:
                self.visual_builder = vb  # type: ignore[assignment]
                try:
                    self.visual_builder.compiledMappingChanged.connect(self._on_visual_builder_live)  # type: ignore
                except Exception:
                    pass
        except Exception as e:
            import traceback as _tb

            err = f"{e.__class__.__name__}: {e}"
            short_tb = "".join(_tb.format_exception_only(type(e), e)).strip()
            self.visual_builder = QLabel(f"Visual builder import error: {err}\n{short_tb}")
        self._editor_stack.addWidget(self.visual_builder)

        self._intent_sidebar = RuleIntentSidebar()
        self._intent_sidebar.setMinimumWidth(260)
        self._watchlist_panel = SelectorWatchlistPanel()
        self._watchlist_panel.setMinimumWidth(260)
        self._side_tabs = QTabWidget()
        self._side_tabs.setObjectName("ingestionLabSideTabs")
        self._side_tabs.addTab(self._intent_sidebar, "Intent")
        self._side_tabs.addTab(self._watchlist_panel, "Watchlist")
        self._side_tabs.addTab(self._sandbox_tab, "Sandbox")
        self._editor_split = QSplitter(Qt.Orientation.Horizontal, self)
        self._editor_split.addWidget(self._editor_stack_container)
        self._editor_split.addWidget(self._side_tabs)
        self._editor_split.setStretchFactor(0, 4)
        self._editor_split.setStretchFactor(1, 2)
        mid_split.addWidget(self._editor_split)

        self._preview_container = QWidget()
        self._preview_stack = QStackedLayout(self._preview_container)
        self.preview_area = QTextEdit()
        self.preview_area.setObjectName("ingestionLabPreview")
        self.preview_area.setReadOnly(True)
        self.preview_area.setPlaceholderText("Select a file then click Preview to see metadata.")
        try:
            from gui.services.service_locator import services as _svc

            if not _svc.try_get("theme_service"):
                self.preview_area.setStyleSheet(
                    "QTextEdit#ingestionLabPreview { background:#111111; color:#e0e0e0; font-family:Consolas,'Courier New',monospace; font-size:12px; }"
                )
        except Exception:
            self.preview_area.setStyleSheet(
                "QTextEdit#ingestionLabPreview { background:#111111; color:#e0e0e0; font-family:Consolas,'Courier New',monospace; font-size:12px; }"
            )
        self._preview_stack.addWidget(self.preview_area)
        if SkeletonLoaderWidget:
            self._batch_skeleton = SkeletonLoaderWidget("table-row", rows=4, shimmer=True)
            self._preview_stack.addWidget(self._batch_skeleton)
        else:
            ph = QLabel("Loading batch preview…")
            ph.setObjectName("ingestionLabBatchFallback")
            self._batch_skeleton = ph  # type: ignore
            self._preview_stack.addWidget(ph)
        self._preview_stack.setCurrentIndex(0)
        mid_split.addWidget(self._preview_container)

        self.log_area = QPlainTextEdit()
        self.log_area.setObjectName("ingestionLabLog")
        self.log_area.setReadOnly(True)
        self.log_area.setPlaceholderText(
            "Execution log will appear here (rule validation, parse results)."
        )
        try:
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

        self.btn_refresh.clicked.connect(self.refresh_file_list)  # type: ignore
        self.btn_preview.clicked.connect(self._on_preview_clicked)  # type: ignore
        self.btn_example_rows.clicked.connect(self._on_example_rows_clicked)  # type: ignore
        self.btn_watchlist.clicked.connect(self._on_watchlist_run_clicked)  # type: ignore
        self.btn_hash_impact.clicked.connect(self._on_hash_impact_clicked)  # type: ignore
        self.btn_field_coverage.clicked.connect(self._on_field_coverage_clicked)  # type: ignore
        try:
            self.btn_field_coverage_radar.clicked.connect(
                self._on_field_coverage_radar_clicked
            )  # type: ignore
        except Exception:
            pass
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
        self.btn_overlap.clicked.connect(self._on_overlap_clicked)  # type: ignore
        self.btn_visual_builder.clicked.connect(self._on_visual_builder_clicked)  # type: ignore
        self.btn_bulk_edit.clicked.connect(self._on_bulk_edit_clicked)  # type: ignore
        self.btn_publish.clicked.connect(self._on_publish_clicked)  # type: ignore
        self.btn_toggle_density.clicked.connect(lambda _v: None)
        self.btn_sandbox_parse.clicked.connect(self._on_sandbox_parse_clicked)  # type: ignore
        self.btn_sandbox_clear.clicked.connect(self._on_sandbox_clear_clicked)  # type: ignore
        self._intent_sidebar.saveRequested.connect(self._on_intent_save)  # type: ignore
        self._intent_sidebar.resourceChanged.connect(self._on_intent_resource_changed)  # type: ignore
        self._watchlist_panel.addWatchRequested.connect(self._on_watchlist_add_requested)  # type: ignore
        self._watchlist_panel.removeRequested.connect(
            self._on_watchlist_remove_requested
        )  # type: ignore
        self._watchlist_panel.setBaselineRequested.connect(
            self._on_watchlist_set_baseline_requested
        )  # type: ignore
        self._watchlist_panel.runRequested.connect(self._on_watchlist_run_clicked)  # type: ignore
        self.search_box.textChanged.connect(lambda _t: self._apply_filters())  # type: ignore
        self.min_size.valueChanged.connect(lambda _v: self._apply_filters())  # type: ignore
        self.max_size.valueChanged.connect(lambda _v: self._apply_filters())  # type: ignore
        self.modified_within_hours.valueChanged.connect(lambda _v: self._apply_filters())  # type: ignore

        self._all_file_items = []
        self._last_field_coverage = None  # type: ignore[assignment]
        try:
            self._safe_guard = SafeApplyGuard()
        except Exception:
            self._safe_guard = None
        self._last_simulation_id = None
        self._banner = QLabel("")
        self._banner.setObjectName("ingestionLabBanner")
        self._banner.setStyleSheet(
            "#ingestionLabBanner { border:1px solid #888; padding:4px; border-radius:4px; background: rgba(200,200,200,0.15); }"
        )
        self._banner.setVisible(False)
        try:
            from gui.design.icon_registry import get_icon  # type: ignore

            icon_map = {
                "btn_refresh": "refresh",
                "btn_preview": "eye",
                "btn_example_rows": "wand",
                "btn_hash_impact": "hash",
                "btn_field_coverage": "table",
                "btn_field_coverage_radar": "radar",
                "btn_orphan_fields": "warning",
                "btn_quality_gates": "shield",
                "btn_simulate": "play",
                "btn_apply": "check",
                "btn_versions": "history",
                "btn_rollback": "undo",
                "btn_export": "export",
                "btn_import": "import",
                "btn_selector_picker": "cursor",
                "btn_regex_tester": "regex",
                "btn_derived": "function",
                "btn_dep_graph": "graph",
                "btn_benchmark": "speed",
                "btn_cache": "database",
                "btn_security": "lock",
                "btn_visual_builder": "layout",
                "btn_prompt_assist": "sparkle",
                "btn_publish": "upload",
                "btn_toggle_density": "density",
                "btn_bulk_edit": "edit",
            }
            for attr, name in icon_map.items():
                btn = getattr(self, attr, None)
                if btn:
                    if isinstance(btn, QAbstractButton) and btn not in self._button_text_cache:
                        self._button_text_cache[btn] = btn.text()
                    if isinstance(btn, QToolButton) and btn not in self._toolbutton_style_cache:
                        try:
                            self._toolbutton_style_cache[btn] = btn.toolButtonStyle()
                        except Exception:
                            pass
                    ic = get_icon(name, size=16)
                    if ic:
                        btn.setIcon(ic)
                        if isinstance(btn, QAbstractButton) and btn not in self._icon_buttons:
                            self._icon_buttons.append(btn)
        except Exception:
            pass

        for btn in self.findChildren(QAbstractButton):
            if btn not in self._button_text_cache:
                try:
                    self._button_text_cache[btn] = btn.text()
                except Exception:
                    continue
            if isinstance(btn, QToolButton) and btn not in self._toolbutton_style_cache:
                try:
                    self._toolbutton_style_cache[btn] = btn.toolButtonStyle()
                except Exception:
                    pass
            try:
                ic = btn.icon()
                if ic and not ic.isNull() and btn not in self._icon_buttons:
                    self._icon_buttons.append(btn)
            except Exception:
                continue

        self._update_compact_icon_labels()

        self._last_apply_summary = {}
        self._last_version_num = None
        try:
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
            )
        self._perf_badge = QLabel("")
        self._perf_badge.setObjectName("ingestionLabPerfBadge")
        self._perf_badge.setStyleSheet(
            "#ingestionLabPerfBadge { border:1px solid #c77; background:rgba(200,40,40,0.15);"
            " padding:2px 6px; border-radius:4px; font-size:11px; color:#a00; }"
        )
        self._perf_badge.setVisible(False)
        self._perf_badge_active = False
        actions.addWidget(self._perf_badge)
        actions.addWidget(self._banner)

        self._register_shortcuts()
        self._configure_keyboard_focus()

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
        except Exception:
            self._draft_timer = None  # type: ignore
        self.rule_editor.textChanged.connect(self._on_rule_text_changed)  # type: ignore
        self._load_existing_draft()
        self._refresh_intent_resources()
        self.batch_preview_skeleton_min_files = int(
            os.environ.get("RP_ING_BATCH_SKELETON_MIN_FILES", "5")
        )
        self.batch_preview_artificial_delay_ms = int(os.environ.get("RP_ING_BATCH_DELAY_MS", "0"))
        self._batch_skeleton_last_shown = False
        self._editor_mode = 0
        self._vb_marker_begin = "# --- Visual Builder Draft BEGIN ---"
        self._vb_marker_end = "# --- Visual Builder Draft END ---"
        self._last_preview_plain = ""
        try:
            from PyQt6.QtCore import QTimer

            self._selector_timer = QTimer(self)
            self._selector_timer.setInterval(250)
            self._selector_timer.setSingleShot(True)
            self._selector_timer.timeout.connect(self._apply_selector_from_cursor)  # type: ignore
            self.rule_editor.cursorPositionChanged.connect(self._on_editor_cursor_changed)  # type: ignore
        except Exception:
            self._selector_timer = None

        try:
            from PyQt6.QtCore import QTimer as _QTimer

            self._intent_refresh_timer = _QTimer(self)
            self._intent_refresh_timer.setInterval(500)
            self._intent_refresh_timer.setSingleShot(True)
            self._intent_refresh_timer.timeout.connect(self._refresh_intent_resources)  # type: ignore
        except Exception:
            self._intent_refresh_timer = None

        try:
            if not os.environ.get("RP_TEST_MODE"):
                self.setStyleSheet(
                    self.styleSheet()
                    + "\n#ingLabToolbarContainer { background: rgba(18,27,36,0.95); border-bottom:1px solid rgba(255,255,255,0.07); }"
                )
        except Exception:
            pass

    def resizeEvent(self, event):  # pragma: no cover - UI behavior
        super().resizeEvent(event)
        try:
            self._reflow_toolbar()
        except Exception:
            pass

    def _reflow_toolbar(self) -> None:
        if not hasattr(self, "_analysis_panel"):
            return
        width = self._action_container.width()
        if width <= 0:
            return
        narrow = width < 1100
        if narrow and not self._toolbar_row2_widget.isVisible():
            self._actions_layout.removeWidget(self._analysis_panel)
            self._toolbar_row2.addWidget(self._analysis_panel)
            self._toolbar_row2_widget.setVisible(True)
        elif width > 1250 and self._toolbar_row2_widget.isVisible():
            self._toolbar_row2.removeWidget(self._analysis_panel)
            insert_idx = self._actions_layout.indexOf(self._filters_widget)
            if insert_idx < 0:
                self._actions_layout.addWidget(self._analysis_panel)
            else:
                self._actions_layout.insertWidget(insert_idx, self._analysis_panel)
            self._toolbar_row2_widget.setVisible(False)

    def _on_visual_builder_clicked(self) -> None:  # pragma: no cover - UI interaction
        if self._editor_mode == 0:
            self._editor_stack.setCurrentIndex(1)
            self._editor_mode = 1
            self.btn_visual_builder.setText("Text Editor")
        else:
            try:
                mapping = getattr(self.visual_builder, "compile_to_mapping", lambda: None)()
            except Exception:
                mapping = None
            if mapping:
                self._inject_visual_builder_snippet(mapping)
            self._editor_stack.setCurrentIndex(0)
            self._editor_mode = 0
            self.btn_visual_builder.setText("Visual Builder")

    def _on_bulk_edit_clicked(self) -> None:  # pragma: no cover - UI invocation path
        try:
            import json as _json
            from gui.ingestion.bulk_edit_dialog import BulkEditDialog  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency missing
            self._append_log(f"Bulk edit import failed: {exc}")
            return

        try:
            if getattr(self, "_editor_mode", 0) == 1:
                rules_payload = self._extract_visual_builder_json() or {}
            else:
                txt = self.rule_editor.toPlainText() or "{}"
                rules_payload = _json.loads(txt)
        except Exception as exc:
            self._append_log(f"Bulk edit aborted: rule parse error: {exc}")
            return

        dlg = BulkEditDialog(rules_payload, self)
        if not dlg.exec():
            return
        modified = dlg.modified_rules()
        if not modified:
            return
        try:
            pretty = _json.dumps(modified, indent=2, sort_keys=True)
        except Exception:
            pretty = _json.dumps(modified)
        self.rule_editor.setPlainText(pretty)
        self._refresh_intent_resources()
        self._append_log("Bulk edit applied to selected fields")

    def _inject_visual_builder_snippet(self, mapping: dict | None, force: bool = False) -> None:
        if not mapping:
            return
        try:
            import json as _json

            resources = mapping.get("resources", {})
            payload = _json.dumps(resources, indent=2, ensure_ascii=False)
            snippet = "# Visual Builder Draft Resources\n" + payload
        except Exception:
            return
        full = self.rule_editor.toPlainText()
        begin, end = self._vb_marker_begin, self._vb_marker_end
        if begin in full and end in full:
            head, rest = full.split(begin, 1)
            block, tail = rest.split(end, 1)
            if not force and snippet in block:
                return
            new_text = head.rstrip() + f"\n{begin}\n{snippet}\n{end}\n" + tail.lstrip()
        else:
            if snippet in full and not force:
                return
            new_text = full.rstrip() + f"\n\n{begin}\n{snippet}\n{end}\n"
        self.rule_editor.setPlainText(new_text)

    def _extract_visual_builder_json(self) -> dict | None:
        begin, end = self._vb_marker_begin, self._vb_marker_end
        text = self.rule_editor.toPlainText()
        if begin not in text or end not in text:
            return None
        try:
            _, rest = text.split(begin, 1)
            block, _ = rest.split(end, 1)
        except ValueError:
            return None
        snippet = block.strip()
        if not snippet:
            return None
        try:
            import json as _json

            cleaned = "\n".join(
                line for line in snippet.splitlines() if not line.strip().startswith("#")
            ).strip()
            if not cleaned:
                return None
            resources = _json.loads(cleaned)
        except Exception:
            return None
        if not isinstance(resources, dict):
            return None
        return {"resources": resources}

    def _on_visual_builder_live(self, mapping: dict) -> None:  # pragma: no cover
        self._inject_visual_builder_snippet(mapping, force=False)

    def _on_editor_cursor_changed(self) -> None:  # pragma: no cover
        if getattr(self, "_selector_timer", None):
            self._selector_timer.stop()
            self._selector_timer.start()

    def _apply_selector_from_cursor(self) -> None:  # pragma: no cover
        try:
            cursor = self.rule_editor.textCursor()
            cursor.select(cursor.SelectionType.WordUnderCursor)
            word = cursor.selectedText()
        except Exception:
            word = ""
        if not word or len(word) < 2:
            return
        if not any(word.startswith(p) for p in (".", "#", "table", "div", "tr", "td")):
            return
        if not self._last_preview_plain:
            return
        parts = self._last_preview_plain.split("--- Snippet ---", 1)
        if len(parts) != 2:
            return
        meta, snippet = parts
        import html as _html

        esc_snip = _html.escape(snippet)
        esc_word = _html.escape(word)
        highlighted = esc_snip.replace(
            esc_word,
            f"<span style='background:#364fa3;color:#fff;padding:1px 2px;border-radius:2px;'>{esc_word}</span>",
        )
        broader = word.rsplit(" ", 1)[0] if " " in word else "(n/a)"
        narrower = word + " td" if not word.endswith(" td") else word + " span"
        suggestion_html = (
            "<div style='margin-top:4px;font-size:11px;color:#aaa;'>Broader: <code>"
            f"{_html.escape(broader)}</code> | Narrower: <code>{_html.escape(narrower)}</code></div>"
        )
        full_html = (
            f"<pre style='font-family:Consolas,monospace;font-size:12px;'>{_html.escape(meta)}--- Snippet ---{highlighted}</pre>"
            + suggestion_html
        )
        try:
            self.preview_area.setHtml(full_html)
        except Exception:
            pass

    def run_accessibility_audit(self):  # pragma: no cover
        try:
            from gui.services.accessibility_audit import audit_widget_tree  # type: ignore
        except Exception:
            return None
        return audit_widget_tree(self)

    def _register_shortcuts(self) -> None:
        try:
            from gui.services.shortcut_registry import global_shortcut_registry as _reg
        except Exception:
            _reg = None

        def _reg_if(sid: str, seq: str, desc: str) -> None:
            if _reg:
                _reg.register(sid, seq, desc, category="Ingestion Lab")
            QShortcut(QKeySequence(seq), self, activated=lambda: self._dispatch_shortcut(sid))

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

    def _dispatch_shortcut(self, sid: str) -> None:
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
            except Exception as exc:
                self._append_log(f"Shortcut '{sid}' failed: {exc}")

    def _configure_keyboard_focus(self) -> None:
        self.file_tree.keyPressEvent = self._wrap_tree_keypress(self.file_tree.keyPressEvent)

    def _wrap_tree_keypress(self, original):  # pragma: no cover - GUI event path
        def _handler(event):
            try:
                from PyQt6.QtGui import QKeyEvent

                _key_event = QKeyEvent  # noqa: F841 - import guard
            except Exception:
                return original(event)
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._on_preview_clicked()
                return
            return original(event)

        return _handler

    def _append_log(self, line: str) -> None:
        self.log_area.appendPlainText(line)
        try:
            from gui.services.service_locator import services as _svc
            from gui.services.event_bus import GUIEvent, EventBus

            bus: EventBus | None = _svc.try_get("event_bus")
            if not bus:
                return
            if "Rule validation failed" in line or line.startswith("Rule validation failed"):
                bus.publish(GUIEvent.RULE_VALIDATION_FAILED, {"error": line})
        except Exception:
            pass

    def base_dir(self) -> str:
        return self._base_dir

    def _now(self) -> float:
        return time.perf_counter()

    def _update_performance_badge(self, elapsed_ms: float) -> None:
        thresh = self.preview_perf_threshold_ms
        if elapsed_ms > thresh:
            self._perf_badge.setText(f"Preview {elapsed_ms:.1f}ms (> {thresh:.0f}ms threshold)")
            self._perf_badge.setVisible(True)
            self._perf_badge_active = True
        else:
            self._perf_badge.setVisible(False)
            self._perf_badge_active = False

    def on_theme_changed(self, theme, changed_keys):  # type: ignore[override]
        try:
            self._apply_density_and_theme()
        except Exception:
            pass

    def _on_density_toggled(self, checked: bool, persist: bool = True) -> None:
        try:
            if persist:
                s = QSettings("RosterPlanner", "IngestionLab")
                s.setValue("compact_density", bool(checked))
        except Exception:
            pass
        self._update_compact_icon_labels()
        self._apply_density_and_theme()

    def _update_compact_icon_labels(self) -> None:
        compact = bool(
            getattr(self, "btn_toggle_density", None) and self.btn_toggle_density.isChecked()
        )
        icon_buttons = getattr(self, "_icon_buttons", [])
        text_map = getattr(self, "_button_text_cache", {})
        style_map = getattr(self, "_toolbutton_style_cache", {})
        for btn, original in text_map.items():
            has_icon = btn in icon_buttons
            try:
                if compact and has_icon:
                    if btn.text():
                        btn.setText("")
                    if not btn.toolTip():
                        btn.setToolTip(original)
                    if isinstance(btn, QToolButton):
                        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
                else:
                    if btn.text() != original:
                        btn.setText(original)
                    if isinstance(btn, QToolButton):
                        restore = style_map.get(btn, Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
                        btn.setToolButtonStyle(restore)
            except Exception:
                continue

    def _apply_density_and_theme(self) -> None:
        try:
            from gui.services.service_locator import services as _svc

            theme = _svc.try_get("theme_service")
            density = _svc.try_get("density_service")
            rc_mode = _svc.try_get("reduced_color_mode")
            hc_mode = _svc.try_get("high_contrast_mode")
        except Exception:
            theme = density = rc_mode = hc_mode = None
        base_margin = 6
        if density:
            try:
                sp_map = density.spacing()
                base_margin = sp_map.get("md", sp_map.get("base", base_margin))
            except Exception:
                pass
        lay = self.layout()
        if isinstance(lay, QVBoxLayout):
            lay.setContentsMargins(base_margin, base_margin, base_margin, base_margin)
            lay.setSpacing(max(4, base_margin - 2))
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
        rc_active = bool(rc_mode and getattr(rc_mode, "is_active", lambda: False)())
        hc_active = bool(hc_mode and getattr(hc_mode, "is_active", lambda: False)())
        self.setProperty("reducedColor", "1" if rc_active else "0")
        self.setProperty("highContrast", "1" if hc_active else "0")
        if hc_active:
            parts.append(
                "#ingestionLabPanel QTextEdit#ingestionLabPreview, "
                "#ingestionLabPanel QPlainTextEdit#ingestionLabLog, "
                "#ingestionLabPanel QPlainTextEdit#ingestionLabRuleEditor { "
                "background:#000000; color:#FFFFFF; selection-background-color:#FFFFFF; selection-color:#000000; }"
            )
        if rc_active:
            parts.append(
                "#ingestionLabPanel QTreeWidget, #ingestionLabPanel QTextEdit, #ingestionLabPanel QPlainTextEdit {"
                " border-color: #666; }"
            )
        compact = bool(
            getattr(self, "btn_toggle_density", None) and self.btn_toggle_density.isChecked()
        )
        pad = 2 if compact else 4
        font_size = 11 if compact else 12
        parts.append(
            f"#ingLabToolbarContainer QPushButton, #ingLabToolbarContainer QToolButton {{ padding:{pad}px {pad+2}px; font-size:{font_size}px; }}"
        )
        if parts:
            if theme and fg and bg:
                try:
                    colors = theme.colors()  # type: ignore[attr-defined]
                except Exception:
                    colors = {}
                surf = colors.get("surface.card", colors.get("background.secondary", bg))
                editor_bg = colors.get("background.editor", surf)
                log_bg = colors.get("background.console", surf)
                prev_bg = colors.get("background.preview", surf)
                toolbar_bg = colors.get("background.toolbar", bg)
                alt = colors.get("surface.sunken", surf)
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
                parts.append(
                    f"#ingLabToolbarContainer {{ background:{toolbar_bg}; border-bottom:1px solid {border_col}; }}"
                )
                parts.append(
                    f"#ingLabToolbarContainer QToolButton, #ingLabToolbarContainer QPushButton {{ color:{fg}; background:transparent; }}"
                )
                parts.append(
                    "#ingLabToolbarContainer QWidget#ingLabCatPanel {"
                    " background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 rgba(255,255,255,0.04), stop:1 rgba(255,255,255,0.02));"
                    f" border:1px solid {border_col}; border-radius:8px;"
                    " margin:0 4px;"
                    "}"
                )
                parts.append(
                    "#ingLabToolbarContainer QWidget#ingLabCatPanel:hover {"
                    " background: qlineargradient(x1:0,y1:0,x2:0,y2=1, stop:0 rgba(255,255,255,0.08), stop:1 rgba(255,255,255,0.04));"
                    "}"
                )
                parts.append(
                    "#ingLabToolbarContainer QLabel#ingLabGroupLabel {"
                    " background: transparent; font-size:11px; letter-spacing:0.5px; text-transform:uppercase;"
                    " font-weight:600; padding:2px 4px 0 4px; color:rgba(255,255,255,0.72);"
                    "}"
                )
                parts.append(
                    f"#ingLabToolbarContainer QWidget#ingLabCatPanel QPushButton, #ingLabToolbarContainer QWidget#ingLabCatPanel QToolButton {{ background:rgba(255,255,255,0.05); border:1px solid {border_col}; border-radius:4px; padding:4px 8px; }}"
                )
                parts.append(
                    f"#ingLabToolbarContainer QWidget#ingLabCatPanel QPushButton:hover, #ingLabToolbarContainer QWidget#ingLabCatPanel QToolButton:hover {{ background:rgba(255,255,255,0.10); border-color:{accent if accent else border_col}; }}"
                )
                parts.append(
                    f"#ingLabToolbarContainer QWidget#ingLabCatPanel QPushButton:pressed, #ingLabToolbarContainer QWidget#ingLabCatPanel QToolButton:pressed {{ background:rgba(255,255,255,0.18); }}"
                )
                parts.append(
                    f"#ingLabToolbarContainer QToolButton#ingLabBtnToggleDensity,"
                    f" #ingLabToolbarContainer QToolButton#ingLabBtnToggleFilters,"
                    f" #ingLabToolbarContainer QToolButton#ingLabBtnOverflow {{ background:{alt}; border:1px solid {border_col}; border-radius:4px; padding:4px 6px; }}"
                )
                parts.append(
                    f"#ingLabToolbarContainer QToolButton#ingLabBtnToggleDensity:hover,"
                    f" #ingLabToolbarContainer QToolButton#ingLabBtnToggleFilters:hover,"
                    f" #ingLabToolbarContainer QToolButton#ingLabBtnOverflow:hover {{ background:{accent if accent else border_col}; color:{fg}; }}"
                )
                parts.append(
                    f"#ingLabToolbarContainer QToolButton#ingLabBtnToggleDensity:checked,"
                    f" #ingLabToolbarContainer QToolButton#ingLabBtnToggleFilters:checked {{ background:{accent if accent else border_col}; color:{fg}; }}"
                )
                parts.append(
                    f"QLineEdit#ingestionLabSearch {{ background:{alt}; color:{fg}; border:1px solid {border_col}; }}"
                )
                parts.append(
                    f"QLineEdit#ingestionLabSearch:focus {{ border-color:{accent if accent else border_col}; }}"
                )
            self.setStyleSheet("\n".join(parts))
