"""Database package exposing schema application helpers.

This package provides utilities for initializing and inspecting the
SQLite database used by RosterPlanner.

Public API:
- apply_schema: Apply the base schema to a sqlite3 connection.
- get_existing_tables: Return a list of existing tables in the database.
- generate_er_mermaid: Produce a Mermaid ER diagram text for documentation.
"""

from .schema import apply_schema, get_existing_tables  # noqa: F401
from .er import generate_er_mermaid  # noqa: F401
from .naming import validate_naming_conventions  # noqa: F401
from .migration_manager import apply_pending_migrations, verify_migration_checksums  # noqa: F401
