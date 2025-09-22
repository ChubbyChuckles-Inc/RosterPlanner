"""Navigation Filter Persistence Service (Milestone 4.3.1)

Persists navigation filtering preferences (search text, division types,
levels, active-only flag) in a small JSON file inside the user data dir
(`base_dir`). Designed similar to `LayoutPersistenceService` but simpler.

Failures are non-fatal; corrupted files are backed up with a suffix.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Set, Optional, Any, Dict
import json
import os
from datetime import datetime

__all__ = [
    "NavigationFilterState",
    "NavigationFilterPersistenceService",
]


FILTER_STATE_VERSION = 1


@dataclass
class NavigationFilterState:
    version: int = FILTER_STATE_VERSION
    search: str = ""
    division_types: Set[str] = None  # type: ignore
    levels: Set[str] = None  # type: ignore
    active_only: bool = False

    def __post_init__(self):
        if self.division_types is None:
            self.division_types = set()
        if self.levels is None:
            self.levels = set()

    def to_json_obj(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "search": self.search,
            "division_types": sorted(self.division_types),
            "levels": sorted(self.levels),
            "active_only": self.active_only,
        }

    @classmethod
    def from_json_obj(cls, obj: Dict[str, Any]) -> "NavigationFilterState":
        if obj.get("version") != FILTER_STATE_VERSION:
            raise ValueError("version mismatch")
        return cls(
            version=obj["version"],
            search=obj.get("search", ""),
            division_types=set(obj.get("division_types", [])),
            levels=set(obj.get("levels", [])),
            active_only=bool(obj.get("active_only", False)),
        )


class NavigationFilterPersistenceService:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def _path(self) -> str:
        return os.path.join(self.base_dir, "navigation_filters.json")

    def load(self) -> NavigationFilterState:
        path = self._path()
        if not os.path.exists(path):
            return NavigationFilterState()
        try:
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            return NavigationFilterState.from_json_obj(obj)
        except Exception:
            # Backup corrupt file
            try:
                backup = path + f".corrupt.{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
                os.replace(path, backup)
            except Exception:  # pragma: no cover
                pass
            return NavigationFilterState()

    def save(self, state: NavigationFilterState) -> bool:
        path = self._path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(state.to_json_obj(), f, indent=2)
            return True
        except Exception:
            return False
