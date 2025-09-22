"""Database package exposing schema application helpers.

This package provides utilities for initializing and inspecting the
SQLite database used by RosterPlanner.

Public API:
"""

from .schema import apply_schema, get_existing_tables  # noqa: F401
from .er import generate_er_mermaid  # noqa: F401
from .naming import validate_naming_conventions  # noqa: F401
from .migration_manager import (
    apply_pending_migrations,
    verify_migration_checksums,
    preview_pending_migration_sql,
)  # noqa: F401
from .ingest import ingest_path, hash_html  # noqa: F401
from .integrity import run_integrity_checks  # noqa: F401
from .rebuild import rebuild_database  # noqa: F401
from .repositories import (  # noqa: F401
    DivisionRepository,
    TeamRepository,
    PlayerRepository,
    MatchRepository,
    AvailabilityRepository,
    DivisionReadRepository,
    DivisionWriteRepository,
    TeamReadRepository,
    TeamWriteRepository,
    PlayerReadRepository,
    PlayerWriteRepository,
)

__all__ = [
    "apply_schema",
    "get_existing_tables",
    "generate_er_mermaid",
    "validate_naming_conventions",
    "apply_pending_migrations",
    "verify_migration_checksums",
    "preview_pending_migration_sql",
    "ingest_path",
    "hash_html",
    "run_integrity_checks",
    "rebuild_database",
    # Repositories
    "DivisionRepository",
    "TeamRepository",
    "PlayerRepository",
    "MatchRepository",
    "AvailabilityRepository",
    # Protocol exports
    "DivisionReadRepository",
    "DivisionWriteRepository",
    "TeamReadRepository",
    "TeamWriteRepository",
    "PlayerReadRepository",
    "PlayerWriteRepository",
]
