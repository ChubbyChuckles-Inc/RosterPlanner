"""Tests for :mod:`gui.services.schema_introspection_service`."""

from __future__ import annotations

import sqlite3

import pytest

from gui.services.schema_introspection_service import SchemaIntrospectionService


@pytest.fixture(name="introspection_service")
def fixture_introspection_service() -> tuple[SchemaIntrospectionService, sqlite3.Connection]:
    """Create an in-memory database and return the service alongside its connection."""

    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(
        """
        CREATE TABLE parent (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE child (
            id INTEGER PRIMARY KEY,
            parent_id INTEGER NOT NULL,
            value TEXT,
            FOREIGN KEY(parent_id) REFERENCES parent(id)
                ON DELETE CASCADE
                ON UPDATE NO ACTION
        );

        CREATE INDEX idx_child_parent ON child(parent_id);
        """
    )
    service = SchemaIntrospectionService(conn)
    service.refresh()
    return service, conn


def test_list_tables_excludes_internal(introspection_service: SchemaIntrospectionService) -> None:
    """The service should expose user tables ordered alphabetically."""

    service, _ = introspection_service
    tables = service.list_tables()
    assert tables == ["child", "parent"]


def test_table_info_contains_expected_metadata(
    introspection_service: SchemaIntrospectionService,
) -> None:
    """Table metadata includes columns, PK, FKs, indexes, and row counts."""

    service, _ = introspection_service
    info = service.get_table_info("child")
    assert info is not None
    assert [col.name for col in info.columns] == ["id", "parent_id", "value"]
    assert info.primary_key == ["id"]
    assert info.row_count == 0
    assert len(info.foreign_keys) == 1
    fk = info.foreign_keys[0]
    assert fk.column == "parent_id"
    assert fk.ref_table == "parent"
    assert fk.ref_column == "id"
    assert any(idx.name == "idx_child_parent" for idx in info.indexes)


def test_row_count_cached_until_refresh(introspection_service: SchemaIntrospectionService) -> None:
    """Row counts remain cached until the service refreshes."""

    service, conn = introspection_service
    conn.execute("INSERT INTO parent (name) VALUES ('A')")
    conn.execute("INSERT INTO child (parent_id, value) VALUES (1, 'v')")
    conn.commit()
    info_cached = service.get_table_info("child")
    assert info_cached is not None
    assert info_cached.row_count == 0  # cached snapshot
    service.refresh()
    info_after = service.get_table_info("child")
    assert info_after is not None
    assert info_after.row_count == 1
