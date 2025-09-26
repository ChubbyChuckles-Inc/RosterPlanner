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

    def add_node(self, node: BuilderNode) -> None:
        if any(n.id == node.id for n in self.nodes):
            raise ValueError(f"Duplicate node id: {node.id}")
        self.nodes.append(node)

    def remove_node(self, node_id: str) -> None:
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
        self._build_ui()
        self.refresh()

    # UI ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self.btn_add_selector = QPushButton("Add Selector")
        self.btn_add_field = QPushButton("Add Field")
        self.btn_add_chain = QPushButton("Add Transform Chain")
        self.btn_compile = QPushButton("Compile → Editor")
        self.chk_live = QCheckBox("Live Preview")
        self.chk_live.setObjectName("visualRuleBuilderLivePreview")
        toolbar.addWidget(self.btn_add_selector)
        toolbar.addWidget(self.btn_add_field)
        toolbar.addWidget(self.btn_add_chain)
        toolbar.addStretch(1)
        toolbar.addWidget(self.chk_live)
        toolbar.addWidget(self.btn_compile)
        layout.addLayout(toolbar)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("visualRuleBuilderNodeList")
        layout.addWidget(self.list_widget, 1)
        self.status_label = QLabel("")
        self.status_label.setObjectName("visualRuleBuilderStatus")
        layout.addWidget(self.status_label)

        # Connections
        self.btn_add_selector.clicked.connect(self._on_add_selector)  # type: ignore
        self.btn_add_field.clicked.connect(self._on_add_field)  # type: ignore
        self.btn_add_chain.clicked.connect(self._on_add_chain)  # type: ignore
        self.btn_compile.clicked.connect(self._on_compile_clicked)  # type: ignore
        self.chk_live.stateChanged.connect(self._on_live_preview_toggled)  # type: ignore

    # Actions -------------------------------------------------------------
    def _on_add_selector(self) -> None:
        idx = len([n for n in self.model.nodes if isinstance(n, SelectorNode)]) + 1
        node = SelectorNode(id=f"selector{idx}", kind="selector", label=f"Selector {idx}")
        self.model.add_node(node)
        self.refresh()
        self._maybe_emit_live()

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

    def refresh(self) -> None:
        self.list_widget.clear()
        for node in self.model.nodes:
            item = QListWidgetItem(f"{node.kind}: {getattr(node, 'label', node.id)}")
            self.list_widget.addItem(item)
        self.status_label.setText(f"{len(self.model.nodes)} node(s)")

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
]
