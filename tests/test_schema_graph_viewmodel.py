"""Tests for :mod:`gui.viewmodels.schema_graph_viewmodel`."""

from __future__ import annotations

from typing import Dict, List, Optional

from gui.services.schema_introspection_service import (
    ColumnInfo,
    ForeignKeyInfo,
    TableInfo,
)
from gui.viewmodels.schema_graph_viewmodel import SchemaGraphViewModel


class FakeIntrospection:
    def __init__(self, tables: Dict[str, TableInfo]) -> None:
        self._tables = tables

    def describe_all(self) -> Dict[str, TableInfo]:
        return dict(self._tables)

    def get_table_info(self, name: str) -> Optional[TableInfo]:
        return self._tables.get(name)


def _table(
    name: str,
    *,
    columns: List[ColumnInfo],
    foreign_keys: Optional[List[ForeignKeyInfo]] = None,
) -> TableInfo:
    return TableInfo(
        name=name,
        columns=columns,
        primary_key=[col.name for col in columns if col.pk_position],
        foreign_keys=foreign_keys or [],
        indexes=[],
        row_count=0,
    )


def _col(name: str, *, pk: int = 0) -> ColumnInfo:
    return ColumnInfo(name=name, type="INTEGER", not_null=pk > 0, default=None, pk_position=pk)


def _fk(column: str, ref_table: str, ref_column: str) -> ForeignKeyInfo:
    return ForeignKeyInfo(
        column=column,
        ref_table=ref_table,
        ref_column=ref_column,
        on_update="NO ACTION",
        on_delete="NO ACTION",
        match="NONE",
    )


def test_build_graph_marks_focus_and_related() -> None:
    tables = {
        "parent": _table("parent", columns=[_col("id", pk=1)]),
        "child": _table(
            "child",
            columns=[_col("id", pk=1), _col("parent_id")],
            foreign_keys=[_fk("parent_id", "parent", "id")],
        ),
        "other": _table("other", columns=[_col("id", pk=1)]),
    }
    vm = SchemaGraphViewModel(FakeIntrospection(tables))

    graph = vm.build_graph("child")

    assert graph.nodes["child"].is_focus is True
    assert graph.nodes["parent"].is_related is True
    assert graph.nodes["other"].is_related is False
    assert graph.edges[0].is_focus is True


def test_renderers_include_highlight_details() -> None:
    tables = {
        "parent": _table("parent", columns=[_col("id", pk=1)]),
        "child": _table(
            "child",
            columns=[_col("id", pk=1), _col("parent_id")],
            foreign_keys=[_fk("parent_id", "parent", "id")],
        ),
    }
    vm = SchemaGraphViewModel(FakeIntrospection(tables))
    graph = vm.build_graph("parent")

    dot = vm.render_dot(graph)
    assert "#ffe498" in dot  # focus fill color
    assert '"parent" -> "child"' in dot or '"child" -> "parent"' in dot

    ascii_text = vm.render_ascii(graph)
    assert "* parent (focus)" in ascii_text
    assert "==>" in ascii_text
