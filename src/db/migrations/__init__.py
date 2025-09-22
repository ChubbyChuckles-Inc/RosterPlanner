"""Database migrations package.

Each migration module must define:
- MIGRATION_ID: int (strictly increasing)
- description: str
- upgrade(conn): function applying the migration (atomic inside transaction managed externally)

Naming convention: mXXXX_description.py where XXXX is zero-padded MIGRATION_ID.
"""

from __future__ import annotations
from typing import List, Tuple, Callable
import importlib
import pkgutil

Migration = Tuple[int, str, Callable]


def discover_migrations() -> List[Migration]:
    from . import __path__  # type: ignore

    migrations: List[Migration] = []
    for modinfo in pkgutil.iter_modules(__path__):  # type: ignore
        if not modinfo.name.startswith("m"):
            continue
        module = importlib.import_module(f"db.migrations.{modinfo.name}")
        if not hasattr(module, "MIGRATION_ID"):
            continue
        migrations.append((module.MIGRATION_ID, getattr(module, "description", ""), module.upgrade))
    migrations.sort(key=lambda m: m[0])
    return migrations


__all__ = ["discover_migrations"]
