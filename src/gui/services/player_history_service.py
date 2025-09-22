"""PlayerHistoryService (Milestone 5.9.9)

Provides retrieval of a player's historical performance based on match
data and player roster snapshots. Since full match parsing is not yet
implemented, this service derives a synthetic history from available
LivePZ values across a team's players, ordered by heuristic dates.

Once MatchRepository exposes per-player performance deltas, this service
can be extended to compute real deltas.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
import datetime as _dt

from gui.models import PlayerHistoryEntry, PlayerEntry
from gui.repositories.protocols import PlayerRepository
from gui.services.service_locator import services

__all__ = ["PlayerHistoryService", "PlayerHistoryResult"]


@dataclass(frozen=True)
class PlayerHistoryResult:
    player: PlayerEntry
    entries: List[PlayerHistoryEntry]


class PlayerHistoryService:
    """Compute a player's historical performance entries.

    Current strategy (placeholder until real match data ingestion):
    - Fetch current players for the player's team.
    - Use the player's own `live_pz` as a baseline.
    - Generate up to the last 5 weekly snapshots with synthetic deltas
      using a deterministic pattern seeded by player name hash to ensure
      stable but varied test output.
    - If no live_pz is available, return empty history.
    """

    MAX_ENTRIES = 5

    def __init__(self, players: PlayerRepository | None = None):
        self._players = players or services.try_get("players_repo")  # type: ignore[assignment]

    def load_player_history(self, player: PlayerEntry) -> PlayerHistoryResult:
        # Only gate on live_pz (repo not required for synthetic placeholder)
        if player.live_pz is None:
            return PlayerHistoryResult(player, [])
        # Deterministic pseudo-random delta pattern seeded by name
        seed = sum(ord(c) for c in player.name)
        base_pattern = [5, -3, 0, 4, -2]
        # Rotate pattern based on seed to diversify
        rot = seed % len(base_pattern)
        pattern = base_pattern[rot:] + base_pattern[:rot]
        today = _dt.date.today()
        entries: List[PlayerHistoryEntry] = []
        cumulative = 0
        for i, delta in enumerate(pattern[: self.MAX_ENTRIES]):
            cumulative += delta if delta is not None else 0
            date = today - _dt.timedelta(days=(self.MAX_ENTRIES - i) * 7)
            entries.append(
                PlayerHistoryEntry(
                    iso_date=date.isoformat(),
                    live_pz_delta=delta,
                )
            )
        return PlayerHistoryResult(player, entries)
