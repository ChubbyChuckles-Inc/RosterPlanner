"""Ingestion Rule Dependency Graph (Milestone 7.10.38)

Builds a directed acyclic graph (DAG) of field dependencies across phases:
 - Base fields: extracted directly from HTML (table columns, list fields)
 - Derived fields: defined under the top-level `derived` mapping (added in 7.10.37)
 - Expression transforms (TransformSpec kind='expr') referencing existing fields

The graph is useful for:
 - Detecting cycles introduced by derived fields
 - Determining recomputation order
 - Visualizing which upstream fields feed a selected derived field

For this milestone we provide:
 - Pure function `build_dependency_graph(mapping)` returning adjacency + reverse
 - Cycle detection raising ValueError
 - Simple topological ordering helper
 - Lightweight ChromeDialog viewer showing adjacency lists & order

The dialog intentionally avoids external graph libs to keep dependencies minimal.
"""

from __future__ import annotations

from typing import Dict, Set, Tuple, List, Mapping
import json
import ast

try:  # pragma: no cover
    from gui.components.chrome_dialog import ChromeDialog
except Exception:  # pragma: no cover
    ChromeDialog = object  # type: ignore[misc]

from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLabel,
    QWidget,
)

from .field_dependency_trace import (
    FieldTraceStep,
    TraceBuildError,
    build_field_trace,
    list_derived_fields,
)

__all__ = [
    "build_dependency_graph",
    "topological_order",
    "DependencyGraphDialog",
]


def _gather_base_fields(mapping: Dict) -> Set[str]:
    out: Set[str] = set()
    resources = mapping.get("resources", {}) if isinstance(mapping, dict) else {}
    if isinstance(resources, dict):
        for _r, spec in resources.items():
            if not isinstance(spec, dict):
                continue
            kind = spec.get("kind")
            if kind == "table":
                cols = spec.get("columns") or []
                if isinstance(cols, list):
                    out.update([c for c in cols if isinstance(c, str)])
            elif kind == "list":
                fields = spec.get("fields") or {}
                if isinstance(fields, dict):
                    out.update([k for k in fields.keys() if isinstance(k, str)])
    return out


ALLOWED_NAME_NODE = ast.Name


def _extract_names_from_expr(code: str) -> Set[str]:
    try:
        tree = ast.parse(code, mode="eval")
    except Exception:
        return set()
    names: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
    return names


def build_dependency_graph(mapping: Dict) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
    """Return (adjacency, reverse_adjacency) for field dependencies.

    Edge direction: upstream -> downstream (A -> B means B depends on A).
    Includes base fields (with possible outgoing edges) and derived fields.
    Expression transform dependencies are also considered (ListRule field
    transform chains referencing other field names). Only names matching known
    fields OR previously defined derived fields are retained.
    Raises ValueError if a cycle is detected via DFS.
    """

    base_fields = _gather_base_fields(mapping)
    derived_map = mapping.get("derived") if isinstance(mapping, dict) else {}
    if not isinstance(derived_map, dict):
        derived_map = {}
    # Collect expression transforms
    resources = mapping.get("resources", {}) if isinstance(mapping, dict) else {}
    expr_edges: List[Tuple[str, Set[str]]] = []
    if isinstance(resources, dict):
        for _rname, spec in resources.items():
            if not isinstance(spec, dict):
                continue
            if spec.get("kind") == "list":
                fields = spec.get("fields") or {}
                if isinstance(fields, dict):
                    for fname, fval in fields.items():
                        if not isinstance(fval, dict):
                            continue
                        tlist = fval.get("transforms") or []
                        if isinstance(tlist, list):
                            for t in tlist:
                                if (
                                    isinstance(t, dict)
                                    and t.get("kind") == "expr"
                                    and isinstance(t.get("code"), str)
                                ):
                                    refs = _extract_names_from_expr(t.get("code")) & base_fields
                                    if refs:
                                        expr_edges.append((fname, refs))
    adjacency: Dict[str, Set[str]] = {f: set() for f in base_fields}
    reverse: Dict[str, Set[str]] = {f: set() for f in base_fields}
    # Derived edges
    for dname, expr in derived_map.items():
        if not isinstance(dname, str) or not isinstance(expr, str):
            continue
        refs = _extract_names_from_expr(expr) & (base_fields | set(derived_map.keys()))
        adjacency.setdefault(dname, set())
        reverse.setdefault(dname, set())
        for ref in refs:
            adjacency.setdefault(ref, set()).add(dname)
            reverse.setdefault(dname, set()).add(ref)
    # Transform edges
    for target, refs in expr_edges:
        adjacency.setdefault(target, set())
        reverse.setdefault(target, set())
        for ref in refs:
            adjacency.setdefault(ref, set()).add(target)
            reverse.setdefault(target, set()).add(ref)
    # Cycle detection (DFS white/gray/black)
    color: Dict[str, int] = {n: 0 for n in adjacency.keys()}  # 0=white,1=gray,2=black

    def dfs(node: str, stack: List[str]):  # noqa: ANN001
        if color[node] == 1:
            raise ValueError("Cycle detected: " + " -> ".join(stack + [node]))
        if color[node] == 2:
            return
        color[node] = 1
        for nxt in adjacency.get(node, ()):  # type: ignore
            dfs(nxt, stack + [node])
        color[node] = 2

    for n in list(adjacency.keys()):
        if color[n] == 0:
            dfs(n, [])
    return adjacency, reverse


def topological_order(adjacency: Dict[str, Set[str]]) -> List[str]:
    indeg: Dict[str, int] = {n: 0 for n in adjacency.keys()}
    for src, outs in adjacency.items():
        for dst in outs:
            indeg[dst] = indeg.get(dst, 0) + 1
    queue = [n for n, d in indeg.items() if d == 0]
    order: List[str] = []
    while queue:
        n = queue.pop(0)
        order.append(n)
        for dst in adjacency.get(n, ()):  # type: ignore
            indeg[dst] -= 1
            if indeg[dst] == 0:
                queue.append(dst)
    if len(order) != len(adjacency):  # leftover means cycle (already detected earlier)
        return []
    return order


class DependencyGraphDialog(ChromeDialog):  # type: ignore[misc]
    def __init__(self, rules_text: str, parent=None):  # noqa: D401
        super().__init__(parent, title="Field Dependencies")
        self.setObjectName("DependencyGraphDialog")
        self._rules_text = rules_text
        self._mapping = self._load_mapping(rules_text)
        self._current_trace: List[FieldTraceStep] = []
        try:
            self.resize(720, 560)
        except Exception:  # pragma: no cover
            pass
        lay = self.content_layout() if hasattr(self, "content_layout") else QVBoxLayout(self)
        self._tabs = QTabWidget()
        lay.addWidget(self._tabs, 1)
        self._build_graph_tab()
        self._build_trace_tab()
        btn_row = QHBoxLayout()
        self.btn_close = QPushButton("Close")
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_close)
        lay.addLayout(btn_row)
        try:  # pragma: no cover
            self.btn_close.clicked.connect(self.close)  # type: ignore[attr-defined]
        except Exception:
            pass

    # --- setup helpers -------------------------------------------------
    def _load_mapping(self, rules_text: str) -> Mapping[str, object]:
        try:
            data = json.loads(rules_text or "{}")
        except Exception:
            return {}
        if isinstance(data, Mapping):
            return data
        return {}

    def _build_graph_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel("Adjacency (field -> dependents):"))
        self.list_nodes = QListWidget()
        layout.addWidget(self.list_nodes, 1)
        self.lbl_order = QLabel("Order:")
        layout.addWidget(self.lbl_order)
        self._tabs.addTab(tab, "Graph")
        self._populate_graph()

    def _populate_graph(self) -> None:
        self.list_nodes.clear()
        try:
            adjacency, _rev = build_dependency_graph(self._mapping)
        except ValueError as exc:
            QListWidgetItem(f"ERROR: {exc}", self.list_nodes)
            self.lbl_order.setText("Order: (error)")
            return
        for src in sorted(adjacency.keys()):
            outs = sorted(adjacency.get(src, set()))
            QListWidgetItem(f"{src} -> {', '.join(outs) if outs else '(none)'}", self.list_nodes)
        order = topological_order(adjacency)
        self.lbl_order.setText("Order: " + (" -> ".join(order) if order else "(cycle)"))

    def _build_trace_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        header = QHBoxLayout()
        header.addWidget(QLabel("Derived Field:"))
        self.trace_combo = QComboBox()
        header.addWidget(self.trace_combo, 1)
        layout.addLayout(header)
        self.trace_tree = QTreeWidget()
        self.trace_tree.setColumnCount(4)
        self.trace_tree.setHeaderLabels(["Field", "Type", "Details", "Transforms"])
        layout.addWidget(self.trace_tree, 1)
        info_row = QHBoxLayout()
        self.trace_status = QLabel("Select a derived field to inspect its upstream chain.")
        info_row.addWidget(self.trace_status, 1)
        self.btn_copy_trace = QPushButton("Copy Trace")
        self.btn_copy_trace.setEnabled(False)
        info_row.addWidget(self.btn_copy_trace)
        layout.addLayout(info_row)
        self._tabs.addTab(tab, "Field Trace")
        try:  # pragma: no cover - headless safe
            self.trace_combo.currentTextChanged.connect(self._on_trace_field_changed)  # type: ignore[attr-defined]
            self.btn_copy_trace.clicked.connect(self._copy_trace_to_clipboard)  # type: ignore[attr-defined]
        except Exception:
            pass
        self._populate_trace_options()

    # --- trace logic ---------------------------------------------------
    def _populate_trace_options(self) -> None:
        fields = list_derived_fields(self._mapping)
        self.trace_combo.blockSignals(True)
        self.trace_combo.clear()
        for name in fields:
            self.trace_combo.addItem(name)
        self.trace_combo.blockSignals(False)
        if not fields:
            self.trace_combo.setEnabled(False)
            self.trace_tree.setDisabled(True)
            self.btn_copy_trace.setEnabled(False)
            self.trace_status.setText("No derived fields defined in the rule set.")
        else:
            self.trace_combo.setEnabled(True)
            self.trace_tree.setDisabled(False)
            self.trace_status.setText("Select a derived field to inspect its upstream chain.")
            self._on_trace_field_changed(self.trace_combo.currentText())

    def _on_trace_field_changed(self, name: str) -> None:
        if not name:
            self.trace_tree.clear()
            self.btn_copy_trace.setEnabled(False)
            return
        try:
            steps = build_field_trace(self._mapping, name)
        except TraceBuildError as exc:
            self.trace_tree.clear()
            self.btn_copy_trace.setEnabled(False)
            self.trace_status.setText(f"Trace error: {exc}")
            self._current_trace = []
            return
        self._current_trace = steps
        self._render_trace_steps(steps)
        self.trace_status.setText("Trace ready. Use Copy to place a text summary on the clipboard.")
        self.btn_copy_trace.setEnabled(True)

    def _render_trace_steps(self, steps: List[FieldTraceStep]) -> None:
        self.trace_tree.clear()
        parents: List[QTreeWidgetItem] = []
        for step in steps:
            item = QTreeWidgetItem()
            item.setText(0, step.name)
            item.setText(1, step.type.replace("_", " "))
            item.setText(2, self._format_step_detail(step))
            item.setText(3, self._format_step_transforms(step))
            if step.note:
                item.setToolTip(0, step.note)
                item.setToolTip(2, step.note)
            while len(parents) > step.depth:
                parents.pop()
            if step.depth == 0 or not parents:
                self.trace_tree.addTopLevelItem(item)
                parents = [item]
            else:
                parents[-1].addChild(item)
                parents.append(item)
        self.trace_tree.expandAll()

    def _format_step_detail(self, step: FieldTraceStep) -> str:
        if step.type == "derived":
            detail = step.expression or ""
        elif step.type == "list_field":
            selector = step.selector or "(no selector)"
            detail = f"{step.resource} → {selector}" if step.resource else selector
        elif step.type == "table_column":
            detail = f"{step.resource} (table column)" if step.resource else "table column"
        else:
            detail = step.note or ""
        return detail

    def _format_step_transforms(self, step: FieldTraceStep) -> str:
        if not step.transforms:
            return ""
        parts = [transform.describe() for transform in step.transforms]
        return ", ".join(parts)

    def _copy_trace_to_clipboard(self) -> None:
        if not self._current_trace:
            return
        lines: List[str] = []
        for step in self._current_trace:
            indent = "  " * step.depth
            line = f"{indent}- {step.name} [{step.type}]"
            detail = self._format_step_detail(step)
            if detail:
                line += f" :: {detail}"
            transforms = self._format_step_transforms(step)
            if transforms:
                line += f" | transforms: {transforms}"
            if step.note and step.note not in detail:
                line += f" ({step.note})"
            lines.append(line)
        text = "\n".join(lines)
        try:  # pragma: no cover
            QApplication.clipboard().setText(text)
            self.trace_status.setText("Trace copied to clipboard.")
        except Exception:
            self.trace_status.setText("Failed to access clipboard.")
