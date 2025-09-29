"""Schema relationship graph view-model (Milestone 7.11.4).

Produces a lightweight representation of table/foreign-key relationships
based on the data supplied by :class:`SchemaIntrospectionService`.

The view-model generates a semantic graph (nodes + edges) and can render
it either as Graphviz DOT syntax or as an ASCII fallback suitable for
textual display when the Graphviz toolchain is unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set

from gui.services.schema_introspection_service import (
    ForeignKeyInfo,
    SchemaIntrospectionService,
    TableInfo,
)

__all__ = [
    "GraphNode",
    "GraphEdge",
    "GraphData",
    "SchemaGraphViewModel",
]


@dataclass(frozen=True)
class GraphNode:
    """Represents a table in the relationship graph."""

    name: str
    is_focus: bool = False
    is_related: bool = False


@dataclass(frozen=True)
class GraphEdge:
    """Represents a foreign-key relationship between two tables."""

    source: str
    target: str
    label: str
    is_focus: bool = False


@dataclass(frozen=True)
class GraphData:
    """Container aggregating graph nodes and edges."""

    nodes: Dict[str, GraphNode]
    edges: List[GraphEdge]


class SchemaGraphViewModel:
    """Builds relationship graphs from schema metadata."""

    def __init__(self, introspection: SchemaIntrospectionService) -> None:
        self._introspection = introspection

    # ------------------------------------------------------------------
    # Public API
    def build_graph(self, focus_table: Optional[str] = None) -> GraphData:
        """Return a semantic graph for the current schema.

        Parameters
        ----------
        focus_table:
            Optional table name to highlight. Nodes directly connected to
            ``focus_table`` are marked as related; the connecting edges are
            flagged so renderers can emphasize them.
        """

        tables = self._safe_tables()
        nodes: Dict[str, GraphNode] = {name: GraphNode(name=name) for name in tables}
        edges: List[GraphEdge] = []

        for table_name, table in tables.items():
            for fk in table.foreign_keys:
                if fk.ref_table not in tables:
                    continue
                label = self._format_fk_label(table_name, fk)
                edges.append(
                    GraphEdge(
                        source=table_name,
                        target=fk.ref_table,
                        label=label,
                    )
                )

        if focus_table and focus_table in nodes:
            nodes = self._apply_focus(nodes, edges, focus_table)
            edges = self._mark_focus_edges(edges, focus_table)

        return GraphData(nodes=nodes, edges=edges)

    def render_dot(self, graph: GraphData) -> str:
        """Render the graph to Graphviz DOT syntax."""

        lines: List[str] = [
            "digraph Schema {",
            "  rankdir=LR;",
            "  graph [fontsize=10, fontname=Helvetica, pad=0.2];",
            (
                '  node [shape=box, style="rounded,filled", fillcolor="#f7f9fc", '
                'color="#7f8c8d", fontname=Helvetica];'
            ),
            "  edge [color=#95a5a6, arrowsize=0.6, fontname=Helvetica, fontsize=9];",
        ]

        for node in sorted(graph.nodes.values(), key=lambda n: n.name.lower()):
            attrs: Dict[str, str] = {"label": node.name}
            if node.is_focus:
                attrs.update(
                    {
                        "fillcolor": "#ffe498",
                        "color": "#d35400",
                        "penwidth": "2",
                        "style": "rounded,filled,bold",
                    }
                )
            elif node.is_related:
                attrs.update(
                    {
                        "fillcolor": "#e8f4ff",
                        "color": "#2980b9",
                        "penwidth": "1.5",
                    }
                )
            else:
                attrs.update({"fillcolor": "#f7f9fc"})
            attr_str = ", ".join(f'{key}="{value}"' for key, value in attrs.items())
            lines.append(f'  "{node.name}" [{attr_str}];')

        for edge in graph.edges:
            attrs: Dict[str, str] = {"label": edge.label}
            if edge.is_focus:
                attrs.update({"color": "#d35400", "penwidth": "2", "fontcolor": "#c0392b"})
            attr_str = ", ".join(f'{key}="{value}"' for key, value in attrs.items())
            lines.append(f'  "{edge.source}" -> "{edge.target}" [{attr_str}];')

        lines.append("}")
        return "\n".join(lines)

    def render_ascii(self, graph: GraphData) -> str:
        """Render the graph as a textual fallback representation."""

        if not graph.nodes:
            return "(no tables registered)"

        lines: List[str] = []
        for node in sorted(graph.nodes.values(), key=lambda n: n.name.lower()):
            if node.is_focus:
                prefix = "*"
                suffix = " (focus)"
            elif node.is_related:
                prefix = ">"
                suffix = " (related)"
            else:
                prefix = "-"
                suffix = ""
            lines.append(f"{prefix} {node.name}{suffix}")

        if graph.edges:
            lines.append("")
            for edge in sorted(
                graph.edges,
                key=lambda e: (e.source.lower(), e.target.lower(), e.label.lower()),
            ):
                arrow = "==>" if edge.is_focus else "-->"
                lines.append(f"{edge.source} {arrow} {edge.target} : {edge.label}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    def _safe_tables(self) -> Dict[str, TableInfo]:
        try:
            return self._introspection.describe_all()
        except Exception:
            return {}

    @staticmethod
    def _format_fk_label(table_name: str, fk: ForeignKeyInfo) -> str:
        return f"{table_name}.{fk.column} → {fk.ref_table}.{fk.ref_column}"

    @staticmethod
    def _apply_focus(
        nodes: Dict[str, GraphNode], edges: Iterable[GraphEdge], focus: str
    ) -> Dict[str, GraphNode]:
        updated: Dict[str, GraphNode] = {}
        related: Set[str] = set()
        for edge in edges:
            if edge.source == focus:
                related.add(edge.target)
            if edge.target == focus:
                related.add(edge.source)
        for name, node in nodes.items():
            if name == focus:
                updated[name] = GraphNode(name=name, is_focus=True)
            elif name in related:
                updated[name] = GraphNode(name=name, is_related=True)
            else:
                updated[name] = node
        return updated

    @staticmethod
    def _mark_focus_edges(edges: List[GraphEdge], focus: str) -> List[GraphEdge]:
        marked: List[GraphEdge] = []
        for edge in edges:
            is_focus = edge.source == focus or edge.target == focus
            marked.append(
                GraphEdge(
                    source=edge.source, target=edge.target, label=edge.label, is_focus=is_focus
                )
            )
        return marked
