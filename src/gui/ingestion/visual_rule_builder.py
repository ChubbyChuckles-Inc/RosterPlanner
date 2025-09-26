"""Visual Rule Builder Canvas (Milestone 7.10.A1).

Provides an initial, non-destructive scaffold for a drag‑and‑drop style rule
authoring surface that composes extraction pipelines as blocks:

    Source Block -> Selector Block -> Transform Chain Block -> Field Mapping Block

The goal of this first milestone increment is to:
 - Define lightweight, testable pure-Python data models (BuilderNode hierarchy)
 - Provide serialization to/from dict for persistence & snapshot tests
 - Offer a QWidget (`VisualRuleBuilder`) that renders a vertical list of blocks
   with add/remove/reorder controls (no free‑form drag canvas yet – deferred to
   later enhancements A1 iterative passes)
 - Expose an adapter (`to_rule_set_mapping`) translating the current canvas
   structure into a draft `RuleSet` compatible mapping (re-using existing
   rule_schema structures) so that round‑trip integration with the existing
   Ingestion Lab editor is possible.

This keeps surface area minimal while enabling incremental UI/UX evolution.

Future Extensions (tracked in later authoring tasks):
 - Spatial drag positioning & connection lines
 - Inline selector validation & coverage heat overlays
 - Macro extraction (ties into 7.10.A12)
 - Complexity meter live updates (7.10.A14)

Design Principles:
 - Separation: model layer independent of Qt for headless testing.
 - Determinism: ordering preserved exactly as authored for stable diffs.
 - Safety: No evaluation or DB interaction here; purely structural modeling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Mapping, TYPE_CHECKING
import copy
from collections import deque
import json

# ---------------------------------------------------------------------------
# Model Layer


@dataclass
class BuilderNode:
    """Base class for all canvas nodes.

    Each node contributes (optionally) to a field extraction pipeline. The
    minimal subset required to compile into a RuleSet is represented.
    """

    id: str
    kind: str
    label: str

    def to_mapping(self) -> Dict[str, Any]:  # pragma: no cover - trivial
        return {"id": self.id, "kind": self.kind, "label": self.label}


@dataclass
class SourceNode(BuilderNode):
    """Represents a logical source grouping (e.g., ranking_table html files)."""

    phase: str = ""

    def to_mapping(self) -> Dict[str, Any]:  # noqa: D401
        m = super().to_mapping()
        m["phase"] = self.phase
        return m


@dataclass
class SelectorNode(BuilderNode):
    """Defines a root CSS selector for a resource (table or list)."""

    selector: str = ""
    mode: str = "table"  # or "list"
    item_selector: Optional[str] = None  # only for list mode

    def to_mapping(self) -> Dict[str, Any]:  # noqa: D401
        m = super().to_mapping()
        m.update({"selector": self.selector, "mode": self.mode})
        if self.mode == "list" and self.item_selector:
            m["item_selector"] = self.item_selector
        return m


@dataclass
class TransformChainNode(BuilderNode):
    """Ordered list of value transform identifiers applied to subsequent fields."""

    transforms: List[Dict[str, Any]] = field(default_factory=list)

    def to_mapping(self) -> Dict[str, Any]:  # noqa: D401
        m = super().to_mapping()
        m["transforms"] = list(self.transforms)
        return m


@dataclass
class FieldMappingNode(BuilderNode):
    """Represents a single output field mapping with optional transform chain ref."""

    field_name: str = ""
    selector: str = ""
    # For this initial increment we inline transforms rather than referencing chain nodes
    transforms: List[Dict[str, Any]] = field(default_factory=list)

    def to_mapping(self) -> Dict[str, Any]:  # noqa: D401
        m = super().to_mapping()
        m.update(
            {
                "field_name": self.field_name,
                "selector": self.selector,
                "transforms": list(self.transforms) if self.transforms else [],
            }
        )
        return m


@dataclass
class CanvasModel:
    """Container representing the entire visual builder canvas state.

    The model maintains a simple ordered list of nodes. Validation rules are
    intentionally light for this first version.
    """

    nodes: List[BuilderNode] = field(default_factory=list)
    _undo_stack: deque = field(default_factory=lambda: deque(maxlen=50), repr=False)
    _redo_stack: deque = field(default_factory=lambda: deque(maxlen=50), repr=False)

    # --- Undo/Redo Core -------------------------------------------------
    def _snapshot(self) -> List[BuilderNode]:  # pragma: no cover - trivial
        return copy.deepcopy(self.nodes)

    def _push_undo(self):  # pragma: no cover - trivial
        self._undo_stack.append(self._snapshot())
        self._redo_stack.clear()

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        self._redo_stack.append(self._snapshot())
        self.nodes = self._undo_stack.pop()
        return True

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        self._undo_stack.append(self._snapshot())
        self.nodes = self._redo_stack.pop()
        return True

    # --- History Persistence -------------------------------------------
    def _serialize_nodes(self, nodes: List[BuilderNode]) -> List[Dict[str, Any]]:  # pragma: no cover
        return [n.to_mapping() for n in nodes]

    def export_history(self) -> Dict[str, Any]:  # pragma: no cover - thin
        return {
            "current": self._serialize_nodes(self.nodes),
            "undo": [self._serialize_nodes(s) for s in list(self._undo_stack)],
            "redo": [self._serialize_nodes(s) for s in list(self._redo_stack)],
        }

    def import_history(self, payload: Mapping[str, Any]) -> None:  # pragma: no cover - thin
        try:
            from_nodes = payload.get("current", [])
            undo_nodes = payload.get("undo", [])
            redo_nodes = payload.get("redo", [])
            self.nodes = CanvasModel.from_mapping({"nodes": from_nodes}).nodes
            self._undo_stack.clear()
            for snap in undo_nodes:
                self._undo_stack.append(CanvasModel.from_mapping({"nodes": snap}).nodes)
            self._redo_stack.clear()
            for snap in redo_nodes:
                self._redo_stack.append(CanvasModel.from_mapping({"nodes": snap}).nodes)
        except Exception:
            pass

    def add_node(self, node: BuilderNode) -> None:
        self._push_undo()
        if any(n.id == node.id for n in self.nodes):
            raise ValueError(f"Duplicate node id: {node.id}")
        self.nodes.append(node)

    def remove_node(self, node_id: str) -> None:
        self._push_undo()
        self.nodes = [n for n in self.nodes if n.id != node_id]

    def to_mapping(self) -> Dict[str, Any]:
        return {"nodes": [n.to_mapping() for n in self.nodes]}

    @staticmethod
    def from_mapping(data: Mapping[str, Any]) -> "CanvasModel":
        raw_nodes = data.get("nodes", [])
        nodes: List[BuilderNode] = []
        for obj in raw_nodes:
            if not isinstance(obj, Mapping):  # pragma: no cover - defensive
                continue
            kind = obj.get("kind")
            base_kwargs = dict(id=obj.get("id", ""), kind=kind, label=obj.get("label", kind))
            if kind == "source":
                nodes.append(SourceNode(**base_kwargs, phase=obj.get("phase", "")))
            elif kind == "selector":
                nodes.append(
                    SelectorNode(
                        **base_kwargs,
                        selector=obj.get("selector", ""),
                        mode=obj.get("mode", "table"),
                        item_selector=obj.get("item_selector"),
                    )
                )
            elif kind == "transform_chain":
                nodes.append(
                    TransformChainNode(**base_kwargs, transforms=list(obj.get("transforms", [])))
                )
            elif kind == "field":
                nodes.append(
                    FieldMappingNode(
                        **base_kwargs,
                        field_name=obj.get("field_name", ""),
                        selector=obj.get("selector", ""),
                        transforms=list(obj.get("transforms", [])),
                    )
                )
        return CanvasModel(nodes=nodes)

    # Compilation -----------------------------------------------------------------
    def to_rule_set_mapping(self) -> Dict[str, Any]:
        """Compile current canvas nodes into a RuleSet-compatible mapping.

        Strategy (minimal viable): first encountered selector node becomes a
        resource named after its label or a generic identifier. All subsequent
        field nodes until the next selector node are grouped. Transform chain
        nodes are inlined into each field (future revision may apply referencing).
        """

        resources: Dict[str, Dict[str, Any]] = {}
        current_resource_name: Optional[str] = None
        current_selector: Optional[SelectorNode] = None
        pending_fields: Dict[str, Dict[str, Any]] = {}
        last_chain: Optional[TransformChainNode] = None

        def flush_resource():
            nonlocal current_resource_name, current_selector, pending_fields, last_chain
            if current_selector and pending_fields:
                if current_selector.mode == "table":
                    resources[current_resource_name or current_selector.label or "resource"] = {
                        "kind": "table",
                        "selector": current_selector.selector,
                        "columns": list(pending_fields.keys()),
                    }
                else:
                    # list mode
                    fields_mapping: Dict[str, Any] = {}
                    for fname, spec in pending_fields.items():
                        # transform list already in spec
                        fm: Dict[str, Any] = {"selector": spec["selector"]}
                        if spec.get("transforms"):
                            fm["transforms"] = spec["transforms"]
                        fields_mapping[fname] = fm
                    resources[current_resource_name or current_selector.label or "resource"] = {
                        "kind": "list",
                        "selector": current_selector.selector,
                        "item_selector": current_selector.item_selector or "",
                        "fields": fields_mapping,
                    }
            current_resource_name = None
            current_selector = None
            pending_fields = {}
            last_chain = None

        for node in self.nodes:
            if isinstance(node, SelectorNode):
                # start new resource
                if current_selector:
                    flush_resource()
                current_selector = node
                current_resource_name = node.label or node.id
                pending_fields = {}
                last_chain = None
            elif isinstance(node, TransformChainNode):
                last_chain = node
            elif isinstance(node, FieldMappingNode):
                if not current_selector:
                    # Field without selector context; skip (authoring error) but do not raise
                    continue
                transforms = node.transforms
                if not transforms and last_chain:
                    transforms = last_chain.transforms
                pending_fields[node.field_name or node.label or node.id] = {
                    "selector": node.selector,
                    "transforms": transforms,
                }
        # Flush trailing
        flush_resource()
        return {"version": 1, "resources": resources}

    # Transform utilities -------------------------------------------------
    def add_transform_to_field(
        self,
        field_id: str,
        transform: Dict[str, Any],
        intelligent: bool = True,
    ) -> bool:
        """Attach a transform to a FieldMappingNode by id.

        If intelligent is True, auto-prepend common prerequisite cleanups
        (e.g. 'trim') when adding parsing transforms like 'to_number' or
        'parse_date'. Returns True if applied, False if field not found.
        Duplicate (same 'kind' + shallow equality) transforms are skipped.
        """
        target: Optional[FieldMappingNode] = None
        for n in self.nodes:
            if isinstance(n, FieldMappingNode) and n.id == field_id:
                target = n
                break
        if not target:
            return False
        existing_kinds = {t.get("kind") for t in target.transforms}
        # Intelligent defaults
        prereqs: List[Dict[str, Any]] = []
        if intelligent:
            k = transform.get("kind")
            if k in {"to_number", "parse_date"} and "trim" not in existing_kinds:
                prereqs.append({"kind": "trim"})
            if k == "collapse_whitespace" and "trim" not in existing_kinds:
                prereqs.append({"kind": "trim"})
        # Insert prereqs if not duplicates
        for p in prereqs:
            if p.get("kind") not in existing_kinds:
                target.transforms.append(p)
                existing_kinds.add(p.get("kind"))
        # Finally add main transform if not duplicate
        if transform.get("kind") not in existing_kinds:
            target.transforms.append(transform)
        return True

    # Duplication --------------------------------------------------------
    def duplicate_node(self, node_id: str) -> Optional[BuilderNode]:
        self._push_undo()
        """Duplicate a node, inserting the copy immediately after original.

        Generates a unique id by appending/incrementing a numeric suffix.
        For field nodes also adjusts field_name if collision would occur.
        Returns the new node or None if not found.
        """
        idx = None
        for i, n in enumerate(self.nodes):
            if n.id == node_id:
                idx = i
                original = n
                break
        if idx is None:
            return None
        new_obj = copy.deepcopy(original)
        base = original.id
        suffix = 2
        while any(n.id == f"{base}_{suffix}" for n in self.nodes):
            suffix += 1
        new_obj.id = f"{base}_{suffix}"  # type: ignore
        if isinstance(new_obj, FieldMappingNode):  # adjust field_name to avoid collision
            fname_base = new_obj.field_name or "field"
            f_suffix = 2
            existing_fields = {
                getattr(n, "field_name", None)
                for n in self.nodes
                if isinstance(n, FieldMappingNode)
            }
            while f"{fname_base}_{f_suffix}" in existing_fields:
                f_suffix += 1
            new_obj.field_name = f"{fname_base}_{f_suffix}"  # type: ignore
        self.nodes.insert(idx + 1, new_obj)
        return new_obj


# ---------------------------------------------------------------------------
# Transform Palette (define BEFORE widget so _build_ui can reference it)

TRANSFORM_PALETTE: Dict[str, List[Dict[str, Any]]] = {
    "Text Cleanup": [
        {"kind": "trim", "label": "Trim"},
        {"kind": "collapse_whitespace", "label": "Collapse WS"},
    ],
    "Numeric": [
        {"kind": "to_number", "label": "To Number"},
    ],
    "Date": [
        {"kind": "parse_date", "format": "%Y-%m-%d", "label": "Parse Date"},
    ],
    "Parsing": [
        {"kind": "regex_extract", "pattern": "(.*)", "group": 1, "label": "Regex"},
    ],
    "Expression": [
        {"kind": "expression", "code": "value", "label": "Expr"},
    ],
}

# ---------------------------------------------------------------------------
# Qt Widget Layer (thin for first increment)

try:  # pragma: no cover - optional Qt import isolation for headless tests
    from PyQt6.QtWidgets import (
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QPushButton,
        QListWidget,
        QListWidgetItem,
        QLineEdit,
        QLabel,
        QCheckBox,
    )
    from PyQt6.QtCore import Qt, pyqtSignal
except Exception:  # pragma: no cover
    QWidget = object  # type: ignore

    class _DummySignal:  # pragma: no cover - headless fallback
        def connect(self, *_, **__):
            return None

        def emit(self, *_, **__):
            return None

    def pyqtSignal(*_args, **_kwargs):  # type: ignore
        return _DummySignal()


class VisualRuleBuilder(QWidget):  # pragma: no cover - GUI smoke tested elsewhere
    """Simple vertical block list editor for builder nodes.

    Provides minimal add/remove functionality. Future iterations will add
    drag‑and‑drop reordering and inline validation feedback.
    """

    compiledMappingChanged = pyqtSignal(dict)  # type: ignore

    def __init__(self, model: Optional[CanvasModel] = None, parent: Optional[Any] = None):
        super().__init__(parent)
        self.model = model or CanvasModel()
        self.setObjectName("visualRuleBuilder")
        self._live_preview_enabled = False
        self._headless = False
        self._last_error: Optional[str] = None
        # Guard: if no QApplication instance, skip heavy UI (headless import in tests)
        try:
            from PyQt6.QtWidgets import QApplication  # type: ignore

            if QApplication.instance() is None:  # pragma: no cover - headless safety
                self._headless = True
                self._last_error = (
                    "No QApplication instance; VisualRuleBuilder in headless stub mode"
                )
                return
        except Exception as _e:  # pragma: no cover
            # If even QApplication import fails, treat as headless
            self._headless = True
            self._last_error = f"Qt import failure: {_e}"
            return
        try:
            self._build_ui()
            self._restore_session_state()
            self.refresh()
        except Exception as e:  # pragma: no cover - UI construction failure surfaced upstream
            self._last_error = f"UI build error: {e}"

    # UI ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Primary toolbar (compact)
        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)
        self.btn_add_selector = QPushButton("Selector")
        self.btn_add_selector.setToolTip("Add Selector Node")
        self.btn_add_field = QPushButton("Field")
        self.btn_add_field.setToolTip("Add Field Mapping Node")
        self.btn_add_chain = QPushButton("Chain")
        self.btn_add_chain.setToolTip("Add Transform Chain Node")
        # Icon registry integration (design token based) with graceful fallback
        try:  # pragma: no cover - runtime optional
            from src.gui.utils.icons import apply_token_icon  # type: ignore

            apply_token_icon(self.btn_add_selector, "add.selector")
            apply_token_icon(self.btn_add_field, "add.field")
            apply_token_icon(self.btn_add_chain, "add.chain")
        except Exception:
            # Fallback: leave text-only
            pass
        self.btn_undo = QPushButton("Undo")
        self.btn_undo.setToolTip("Undo last edit (Ctrl+Z)")
        self.btn_redo = QPushButton("Redo")
        self.btn_redo.setToolTip("Redo")
        self.btn_compile = QPushButton("Compile")
        self.btn_compile.setToolTip("Compile current canvas to mapping and emit preview")
        self.chk_live = QCheckBox("Live")
        self.chk_live.setToolTip("Automatically compile after changes")
        self.chk_live.setObjectName("visualRuleBuilderLivePreview")
        toolbar.addWidget(self.btn_add_selector)
        toolbar.addWidget(self.btn_add_field)
        toolbar.addWidget(self.btn_add_chain)
        toolbar.addSpacing(6)
        toolbar.addWidget(self.btn_undo)
        toolbar.addWidget(self.btn_redo)
        toolbar.addSpacing(8)
        toolbar.addWidget(self.chk_live)
        toolbar.addWidget(self.btn_compile)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        # Node + palette splitter
        from PyQt6.QtWidgets import QSplitter, QTabWidget, QScrollArea, QWidget as _QW

        splitter = QSplitter(self)
        splitter.setOrientation(Qt.Orientation.Vertical)

        # Node list section
        node_container = _QW()
        node_v = QVBoxLayout(node_container)
        node_v.setContentsMargins(0, 0, 0, 0)
        node_v.setSpacing(4)
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("visualRuleBuilderNodeList")
        self.list_widget.setMinimumHeight(140)
        node_v.addWidget(self.list_widget)

        # Collapsible palette header
        palette_header_bar = QHBoxLayout()
        palette_header_bar.setSpacing(4)
        self.btn_toggle_palette = QPushButton("Transforms ▾")
        self.btn_toggle_palette.setCheckable(True)
        self.btn_toggle_palette.setChecked(True)
        self.btn_toggle_palette.setObjectName("visualRuleBuilderPaletteToggle")
        palette_header_bar.addWidget(self.btn_toggle_palette)
        palette_header_bar.addStretch(1)
        node_v.addLayout(palette_header_bar)

        # Palette container (tabs)
        self._palette_container = _QW()
        self._palette_container.setObjectName("visualRuleBuilderTransformPalette")
        tab_layout = QVBoxLayout(self._palette_container)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(2)
        self.palette_tabs = QTabWidget(self._palette_container)
        self.palette_tabs.setObjectName("visualRuleBuilderTransformTabs")
        self._palette_buttons: Dict[str, List[Any]] = {}
        for category, items in TRANSFORM_PALETTE.items():
            tab_page = _QW()
            page_layout = QVBoxLayout(tab_page)
            page_layout.setContentsMargins(4, 4, 4, 4)
            page_layout.setSpacing(4)
            # Use flow-like grid (4 per row)
            current_row = QHBoxLayout()
            current_row.setSpacing(4)
            count = 0
            btn_refs: List[Any] = []
            for spec in items:
                b = QPushButton(spec["label"])  # type: ignore[arg-type]
                b.setObjectName(f"transformChip_{spec['kind']}")
                b.setCursor(Qt.CursorShape.PointingHandCursor)

                def _make_handler(s: Dict[str, Any]):  # noqa: WPS430
                    def _handler():  # pragma: no cover
                        self._apply_transform_chip(s)

                    return _handler

                b.clicked.connect(_make_handler(spec))  # type: ignore
                current_row.addWidget(b)
                btn_refs.append(b)
                count += 1
                if count % 4 == 0:
                    page_layout.addLayout(current_row)
                    current_row = QHBoxLayout()
                    current_row.setSpacing(4)
            if current_row.count() > 0:
                page_layout.addLayout(current_row)
            # Scroll area in case many chips later
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            inner_wrap = _QW()
            inner_layout = QVBoxLayout(inner_wrap)
            inner_layout.setContentsMargins(0, 0, 0, 0)
            inner_layout.setSpacing(0)
            inner_layout.addWidget(tab_page)
            scroll.setWidget(inner_wrap)
            self.palette_tabs.addTab(scroll, category)
            self._palette_buttons[category] = btn_refs
        tab_layout.addWidget(self.palette_tabs)
        node_v.addWidget(self._palette_container)

        # Status label at bottom
        self.status_label = QLabel("")
        self.status_label.setObjectName("visualRuleBuilderStatus")
        node_v.addWidget(self.status_label)

        splitter.addWidget(node_container)
        splitter.setStretchFactor(0, 1)
        layout.addWidget(splitter, 1)
        # Field detail editor (appears only for Field nodes)
        self._field_editor = _QW()
        self._field_editor.setObjectName("visualRuleBuilderFieldEditor")
        fe_layout = QHBoxLayout(self._field_editor)
        fe_layout.setContentsMargins(0, 0, 0, 0)
        fe_layout.setSpacing(4)
        from PyQt6.QtWidgets import QFormLayout, QLineEdit

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        self.field_name_edit = QLineEdit()
        self.field_name_edit.setPlaceholderText("field_name")
        self.field_selector_edit = QLineEdit()
        self.field_selector_edit.setPlaceholderText(".css-selector")
        form.addRow("Name", self.field_name_edit)
        form.addRow("Selector", self.field_selector_edit)
        # Validation feedback label
        from PyQt6.QtWidgets import QLabel as _Lbl

        self.selector_feedback = _Lbl("")
        self.selector_feedback.setObjectName("visualRuleBuilderSelectorFeedback")
        form.addRow("Matches", self.selector_feedback)
        fe_layout.addLayout(form)
        layout.addWidget(self._field_editor)
        self._field_editor.hide()
        try:  # connect change handlers
            self.field_name_edit.editingFinished.connect(self._commit_field_name)  # type: ignore
            self.field_selector_edit.editingFinished.connect(self._commit_field_selector)  # type: ignore
        except Exception:  # pragma: no cover
            pass

        # Connections
        self.btn_add_selector.clicked.connect(self._on_add_selector)  # type: ignore
        self.btn_add_field.clicked.connect(self._on_add_field)  # type: ignore
        self.btn_add_chain.clicked.connect(self._on_add_chain)  # type: ignore
        self.btn_undo.clicked.connect(self._on_undo)  # type: ignore
        self.btn_redo.clicked.connect(self._on_redo)  # type: ignore
        self.btn_compile.clicked.connect(self._on_compile_clicked)  # type: ignore
        self.chk_live.stateChanged.connect(self._on_live_preview_toggled)  # type: ignore
        # Selection change hookup (inside build_ui to avoid NameError at class creation)
        try:  # pragma: no cover - safety
            self.list_widget.currentRowChanged.connect(self._on_selection_changed)  # type: ignore
        except Exception:
            pass
        self.btn_toggle_palette.toggled.connect(self._on_palette_toggled)  # type: ignore
        # Node list context menu
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._on_list_context_menu)  # type: ignore
        # Drag reorder
        from PyQt6.QtWidgets import QAbstractItemView

        self.list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        try:
            self.list_widget.model().rowsMoved.connect(self._on_rows_moved)  # type: ignore
        except Exception:
            pass
        # Shortcuts
        from PyQt6.QtGui import QShortcut, QKeySequence

        QShortcut(QKeySequence("Alt+S"), self, activated=self._on_add_selector)  # type: ignore
        QShortcut(QKeySequence("Alt+F"), self, activated=self._on_add_field)  # type: ignore
        QShortcut(QKeySequence("Alt+C"), self, activated=self._on_add_chain)  # type: ignore
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self._on_undo)  # type: ignore
        QShortcut(QKeySequence("Ctrl+Y"), self, activated=self._on_redo)  # type: ignore
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self, activated=self._on_redo)  # type: ignore
        QShortcut(QKeySequence("Ctrl+/"), self, activated=self._show_cheat_sheet)  # type: ignore
        # Load persisted palette state
        self._restore_palette_state()

    # Actions -------------------------------------------------------------
    def _on_add_selector(self) -> None:
        idx = len([n for n in self.model.nodes if isinstance(n, SelectorNode)]) + 1
        node = SelectorNode(id=f"selector{idx}", kind="selector", label=f"Selector {idx}")
        self.model.add_node(node)
        self.refresh()
        self._maybe_emit_live()
        self._persist_session_state()

    def _on_add_field(self) -> None:
        idx = len([n for n in self.model.nodes if isinstance(n, FieldMappingNode)]) + 1
        node = FieldMappingNode(
            id=f"field{idx}",
            kind="field",
            label=f"Field {idx}",
            field_name=f"field_{idx}",
            selector=".col",
        )
        self.model.add_node(node)
        self.refresh()
        self._maybe_emit_live()
        self._persist_session_state()

    def _on_add_chain(self) -> None:
        idx = len([n for n in self.model.nodes if isinstance(n, TransformChainNode)]) + 1
        node = TransformChainNode(
            id=f"chain{idx}",
            kind="transform_chain",
            label=f"Chain {idx}",
            transforms=[{"kind": "trim"}, {"kind": "to_number"}],
        )
        self.model.add_node(node)
        self.refresh()
        self._maybe_emit_live()
        self._persist_session_state()

    def _on_compile_clicked(self) -> None:
        mapping = self.model.to_rule_set_mapping()
        self.status_label.setText(f"Compiled {len(mapping.get('resources', {}))} resource(s)")
        self._last_compiled = mapping  # stored for tests
        self.compiledMappingChanged.emit(mapping)

    def _on_live_preview_toggled(self) -> None:
        self._live_preview_enabled = bool(self.chk_live.isChecked())
        if self._live_preview_enabled:
            self._on_compile_clicked()

    def _maybe_emit_live(self) -> None:
        if getattr(self, "_live_preview_enabled", False):
            self._on_compile_clicked()

    # Selection handling --------------------------------------------------
    def _on_selection_changed(self, row: int) -> None:  # pragma: no cover
        self._selected_node_id = None
        if row < 0 or row >= len(self.model.nodes):
            self._field_editor.hide()
            return
        node = self.model.nodes[row]
        self._selected_node_id = node.id
        if isinstance(node, FieldMappingNode):
            self.field_name_edit.blockSignals(True)
            self.field_selector_edit.blockSignals(True)
            self.field_name_edit.setText(node.field_name)
            self.field_selector_edit.setText(node.selector)
            self.field_name_edit.blockSignals(False)
            self.field_selector_edit.blockSignals(False)
            self._field_editor.show()
        else:
            self._field_editor.hide()

    # Transform chip application -----------------------------------------
    def _apply_transform_chip(self, spec: Dict[str, Any]) -> None:  # pragma: no cover - thin UI
        if not getattr(self, "_selected_node_id", None):
            self.status_label.setText("Select a Field node first")
            return
        applied = self.model.add_transform_to_field(self._selected_node_id, dict(spec))
        if applied:
            self.status_label.setText(
                f"Added transform '{spec.get('kind')}' to {self._selected_node_id}"
            )
            self._maybe_emit_live()
            self.refresh()
        else:
            self.status_label.setText("Transform not applied (not a field node?)")

    def _on_palette_toggled(self, checked: bool) -> None:  # pragma: no cover - trivial
        if checked:
            self._palette_container.show()
            self.btn_toggle_palette.setText("Transforms ▾")
        else:
            self._palette_container.hide()
            self.btn_toggle_palette.setText("Transforms ▸")
        self._persist_palette_state()

    # Drag reorder -------------------------------------------------------
    def _on_rows_moved(self, *_) -> None:  # pragma: no cover - UI event
        # Rebuild model order from list items' stored ids
        id_to_node = {n.id: n for n in self.model.nodes}
        ids: List[str] = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            nid = item.data(Qt.ItemDataRole.UserRole)
            if nid in id_to_node:
                ids.append(nid)
        self.model.nodes = [id_to_node[i] for i in ids if i in id_to_node]
        self._maybe_emit_live()

    # Context menu -------------------------------------------------------
    def _on_list_context_menu(self, pos) -> None:  # pragma: no cover - GUI path
        from PyQt6.QtWidgets import QMenu

        global_pos = self.list_widget.mapToGlobal(pos)
        menu = QMenu(self.list_widget)
        act_dup = menu.addAction("Duplicate")
        act_del = menu.addAction("Delete")
        act = menu.exec(global_pos)
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.model.nodes):
            return
        node = self.model.nodes[row]
        if act == act_dup:
            new_node = self.model.duplicate_node(node.id)
            if new_node:
                self.refresh()
                self.status_label.setText(f"Duplicated {node.id} → {new_node.id}")
                self._maybe_emit_live()
                self._persist_session_state()
        elif act == act_del:
            self.model.remove_node(node.id)
            self.refresh()
            self.status_label.setText(f"Deleted {node.id}")
            self._maybe_emit_live()
            self._persist_session_state()

    # Settings persistence -----------------------------------------------
    def _settings(self):  # pragma: no cover - convenience
        try:
            from PyQt6.QtCore import QSettings

            return QSettings()
        except Exception:
            return None

    def _persist_palette_state(self) -> None:  # pragma: no cover - simple
        s = self._settings()
        if not s:
            return
        try:
            s.setValue("visual_builder/palette_collapsed", not self.btn_toggle_palette.isChecked())
        except Exception:
            pass

    def _restore_palette_state(self) -> None:  # pragma: no cover - simple
        s = self._settings()
        if not s:
            return
        try:
            collapsed = s.value("visual_builder/palette_collapsed", False, type=bool)
            if collapsed:
                # Will trigger persistence again but harmless
                self.btn_toggle_palette.setChecked(False)
        except Exception:
            pass

    # Field editor change handlers --------------------------------------
    def _commit_field_name(self):  # pragma: no cover - UI
        if not getattr(self, "_selected_node_id", None):
            return
        node = next((n for n in self.model.nodes if n.id == self._selected_node_id), None)
        if isinstance(node, FieldMappingNode):
            node.field_name = self.field_name_edit.text().strip() or node.field_name
            self.refresh()
            self._maybe_emit_live()
            self._persist_session_state()

    def _commit_field_selector(self):  # pragma: no cover - UI
        if not getattr(self, "_selected_node_id", None):
            return
        node = next((n for n in self.model.nodes if n.id == self._selected_node_id), None)
        if isinstance(node, FieldMappingNode):
            sel = self.field_selector_edit.text().strip()
            if sel:
                node.selector = sel
                self._update_selector_feedback(sel)
            self._maybe_emit_live()
            self._persist_session_state()

    # Undo/Redo handlers -------------------------------------------------
    def _on_undo(self):  # pragma: no cover - UI
        if self.model.undo():
            self.refresh()
            self._maybe_emit_live()
            self._persist_session_state()

    def _on_redo(self):  # pragma: no cover - UI
        if self.model.redo():
            self.refresh()
            self._maybe_emit_live()
            self._persist_session_state()

    # Selector validation ------------------------------------------------
    def _update_selector_feedback(self, selector: str):  # pragma: no cover - GUI heuristic
        try:
            from bs4 import BeautifulSoup  # type: ignore
            html_doc = getattr(self, "_active_preview_html", None)
            if html_doc is None:
                # backward compatibility fallback
                html_doc = getattr(self.parent(), "_last_preview_html", "") or ""
            if not html_doc:
                self.selector_feedback.setText("?")
                return
            soup = BeautifulSoup(html_doc, "html.parser")
            count = len(soup.select(selector))
            self.selector_feedback.setText(str(count))
        except Exception:
            self.selector_feedback.setText("-")

    def set_preview_html(self, html: str) -> None:  # pragma: no cover - external API
        self._active_preview_html = html
        if getattr(self, "_selected_node_id", None):
            node = next((n for n in self.model.nodes if n.id == self._selected_node_id), None)
            if isinstance(node, FieldMappingNode):
                self._update_selector_feedback(node.selector)

    # Cheat sheet --------------------------------------------------------
    def _show_cheat_sheet(self):  # pragma: no cover - UI dialog
        from PyQt6.QtWidgets import QMessageBox

        msg = QMessageBox(self)
        msg.setWindowTitle("Visual Builder Shortcuts")
        msg.setText(
            """<b>Keyboard Shortcuts</b><br><br>
Alt+S — Add Selector<br>
Alt+F — Add Field<br>
Alt+C — Add Transform Chain<br>
Ctrl+Z — Undo<br>
Ctrl+Y — Redo<br>
Ctrl+/ — Show this cheat sheet<br>
"""
        )
        msg.exec()

    def refresh(self) -> None:
        self.list_widget.clear()
        for node in self.model.nodes:
            item = QListWidgetItem(f"{node.kind}: {getattr(node, 'label', node.id)}")
            self.list_widget.addItem(item)
        self.status_label.setText(f"{len(self.model.nodes)} node(s)")
        # Persist session on any refresh to capture latest state
        self._persist_session_state()

    # Session persistence (model + history) -----------------------------
    def _persist_session_state(self) -> None:  # pragma: no cover - simple
        try:
            from PyQt6.QtCore import QSettings
            s = QSettings()
            payload = self.model.export_history()
            s.setValue("visual_builder/session", json.dumps(payload))
        except Exception:
            pass

    def _restore_session_state(self) -> None:  # pragma: no cover - simple
        try:
            from PyQt6.QtCore import QSettings
            s = QSettings()
            raw = s.value("visual_builder/session", "")
            if not raw:
                return
            data = json.loads(raw)
            if isinstance(data, dict):
                self.model.import_history(data)
        except Exception:
            pass

    # Convenience for tests
    def compile_to_mapping(self) -> Dict[str, Any]:
        return self.model.to_rule_set_mapping()


__all__ = [
    "BuilderNode",
    "SourceNode",
    "SelectorNode",
    "TransformChainNode",
    "FieldMappingNode",
    "CanvasModel",
    "VisualRuleBuilder",
    "TRANSFORM_PALETTE",
]
