"""Persistence layer for player availability planning.

Stores availability per team and date with optional notes.
Schema (JSON):
{
  "teams": {
     "<team_id>": {
        "players": ["Name A", "Name B", ...],
        "dates": {
            "YYYY-MM-DD": {
                "<player_name>": {"status": "available|maybe|unavailable", "note": "..."}
            }
        }
     }
  }
}
"""

from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

DEFAULT_FILENAME = "availability_planning.json"


@dataclass
class PlayerAvailability:
    status: str  # available|maybe|unavailable
    note: str | None = None


@dataclass
class TeamAvailability:
    players: List[str] = field(default_factory=list)
    dates: Dict[str, Dict[str, PlayerAvailability]] = field(default_factory=dict)


@dataclass
class AvailabilityState:
    teams: Dict[str, TeamAvailability] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> "AvailabilityState":
        return cls()

    def ensure_team(self, team_id: str, players: List[str]) -> None:
        entry = self.teams.setdefault(team_id, TeamAvailability())
        # Merge players, preserve order of existing, append new
        existing = set(entry.players)
        for p in players:
            if p not in existing:
                entry.players.append(p)
                existing.add(p)

    def set_player_status(
        self, team_id: str, date: str, player: str, status: str, note: str | None = None
    ) -> None:
        entry = self.teams.setdefault(team_id, TeamAvailability())
        day = entry.dates.setdefault(date, {})
        day[player] = PlayerAvailability(status=status, note=note)

    def export(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"teams": {}}
        for tid, t in self.teams.items():
            data["teams"][tid] = {
                "players": t.players,
                "dates": {
                    d: {p: av.__dict__ for p, av in day.items()} for d, day in t.dates.items()
                },
            }
        return data

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "AvailabilityState":
        state = cls()
        for tid, tdata in raw.get("teams", {}).items():
            tav = TeamAvailability(players=list(tdata.get("players", [])))
            for date, day in tdata.get("dates", {}).items():
                tav.dates[date] = {}
                for player, pdata in day.items():
                    tav.dates[date][player] = PlayerAvailability(
                        status=pdata.get("status", "maybe"), note=pdata.get("note")
                    )
            state.teams[tid] = tav
        return state


def load(path: str) -> AvailabilityState:
    if not os.path.exists(path):
        return AvailabilityState.empty()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        return AvailabilityState.from_dict(raw)
    except Exception:
        return AvailabilityState.empty()


def save(state: AvailabilityState, path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(state.export(), fh, indent=2, ensure_ascii=False)
