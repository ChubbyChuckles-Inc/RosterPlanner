"""Navigation State Persistence Service (Milestone 4.4)

Persists navigation tree UI state:
 - Expanded division labels
 - Last selected team id (if any)

Implemented similar to other persistence services using a small JSON file.
The service is intentionally minimal and independent of Qt widgets so it can
be unit tested easily.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Set, Dict, Any
import json
import os
from datetime import datetime

__all__ = ["NavigationState", "NavigationStatePersistenceService"]

NAV_STATE_VERSION = 1


@dataclass
class NavigationState:
    version: int = NAV_STATE_VERSION
    expanded_divisions: Set[str] = None  # type: ignore
    last_selected_team_id: str | None = None

    def __post_init__(self):
        if self.expanded_divisions is None:
            self.expanded_divisions = set()

    def to_json(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "expanded_divisions": sorted(self.expanded_divisions),
            "last_selected_team_id": self.last_selected_team_id,
        }

    @classmethod
    def from_json(cls, obj: Dict[str, Any]) -> "NavigationState":
        if obj.get("version") != NAV_STATE_VERSION:
            raise ValueError("version mismatch")
        return cls(
            version=obj["version"],
            expanded_divisions=set(obj.get("expanded_divisions", [])),
            last_selected_team_id=obj.get("last_selected_team_id"),
        )


class NavigationStatePersistenceService:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def _path(self) -> str:
        return os.path.join(self.base_dir, "navigation_state.json")

    def load(self) -> NavigationState:
        path = self._path()
        if not os.path.exists(path):
            return NavigationState()
        try:
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            return NavigationState.from_json(obj)
        except Exception:
            # Backup corrupt file and start fresh
            try:
                backup = path + f".corrupt.{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
                os.replace(path, backup)
            except Exception:  # pragma: no cover
                pass
            return NavigationState()

    def save(self, state: NavigationState) -> bool:
        path = self._path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(state.to_json(), f, indent=2)
            return True
        except Exception:
            return False
