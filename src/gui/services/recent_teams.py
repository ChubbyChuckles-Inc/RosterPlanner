"""Recent Teams Tracker (Milestone 4.7)

Maintains a fixed-size MRU (most recently used) list of team selections.
Adjacent duplicates are ignored; re-selecting a team moves it to the front.
Designed to be UI-framework agnostic for easy testing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Iterable

__all__ = ["RecentTeamsTracker"]


@dataclass
class RecentTeamsTracker:
    max_items: int = 10
    _teams: List[str] = field(default_factory=list)  # store team_id list in MRU order

    def add(self, team_id: str):
        if not team_id:
            return
        if self._teams and self._teams[0] == team_id:
            return  # adjacent duplicate
        # If already exists deeper, remove old occurrence
        try:
            self._teams.remove(team_id)
        except ValueError:
            pass
        self._teams.insert(0, team_id)
        # Trim
        if len(self._teams) > self.max_items:
            del self._teams[self.max_items :]

    def items(self) -> List[str]:
        return list(self._teams)

    def clear(self):
        self._teams.clear()
