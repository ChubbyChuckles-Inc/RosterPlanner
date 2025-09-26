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

from typing import Dict, Set, Tuple, List
import json
import ast

try:  # pragma: no cover
    from gui.components.chrome_dialog import ChromeDialog
except Exception:  # pragma: no cover
    ChromeDialog = object  # type: ignore[misc]

from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLabel,
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
        super().__init__(parent, title="Dependency Graph")
        self.setObjectName("DependencyGraphDialog")
        try:
            self.resize(640, 520)
        except Exception:  # pragma: no cover
            pass
        lay = self.content_layout() if hasattr(self, "content_layout") else QVBoxLayout(self)
        self.list_nodes = QListWidget()
        lay.addWidget(QLabel("Adjacency (field -> dependents):"))
        lay.addWidget(self.list_nodes, 1)
        self.lbl_order = QLabel("Order:")
        lay.addWidget(self.lbl_order)
        btn_row = QHBoxLayout()
        self.btn_close = QPushButton("Close")
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_close)
        lay.addLayout(btn_row)
        try:  # pragma: no cover
            self.btn_close.clicked.connect(self.close)  # type: ignore[attr-defined]
        except Exception:
            pass
        self._populate(rules_text)

    def _populate(self, rules_text: str) -> None:
        try:
            mapping = json.loads(rules_text or "{}")
        except Exception:
            mapping = {}
        try:
            adjacency, _rev = build_dependency_graph(mapping)
        except ValueError as e:
            QListWidgetItem(f"ERROR: {e}", self.list_nodes)
            return
        for src in sorted(adjacency.keys()):
            outs = sorted(adjacency.get(src, set()))
            QListWidgetItem(f"{src} -> {', '.join(outs) if outs else '(none)'}", self.list_nodes)
        order = topological_order(adjacency)
        self.lbl_order.setText("Order: " + (" -> ".join(order) if order else "(cycle)"))
