"""Column visibility persistence service (Milestone 5.1.1).

Stores a mapping of column key -> visible bool in JSON. Designed to be
reusable across table-based views. Unknown columns default to visible
when encountered.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Set
import json
import os


@dataclass
class ColumnVisibilityState:
    visible: Dict[str, bool] = field(default_factory=dict)
    version: int = 1

    def is_visible(self, key: str) -> bool:
        return self.visible.get(key, True)

    def set_visible(self, key: str, flag: bool):
        self.visible[key] = flag


class ColumnVisibilityPersistenceService:
    FILENAME = "team_detail_columns.json"

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.path = os.path.join(base_dir, self.FILENAME)

    def load(self) -> ColumnVisibilityState:
        if not os.path.exists(self.path):
            return ColumnVisibilityState()
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if not isinstance(raw, dict):
                return ColumnVisibilityState()
            return ColumnVisibilityState(
                visible=raw.get("visible", {}), version=raw.get("version", 1)
            )
        except Exception:
            return ColumnVisibilityState()

    def save(self, state: ColumnVisibilityState):
        os.makedirs(self.base_dir, exist_ok=True)
        data = {"visible": state.visible, "version": state.version}
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


__all__ = ["ColumnVisibilityState", "ColumnVisibilityPersistenceService"]
