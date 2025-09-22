"""Repository interface layer (Milestone 5.9.1).

This module defines typed `Protocol` interfaces for the data access layer
used by GUI services and viewmodels. Repositories abstract persistence
details (SQLite, in-memory test doubles, future remote APIs) and provide
high-level query methods returning lightweight domain dataclasses.

Design Notes:
- Interfaces are intentionally minimal at this stage (read-focused) to
  support upcoming ingestion wiring (Milestone 5.9.2+). Write / upsert
  operations will be added once ingestion coordinator contracts solidify.
- Domain dataclasses here represent *persisted* entities and may differ
  slightly from GUI presentation models found in `gui.models`. Separation
  avoids leaking persistence-only fields (e.g., internal numeric ids).
- Protocols prefer returning immutable tuples / dataclasses over dicts for
  clarity and static type safety.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol, Sequence, runtime_checkable, Optional

__all__ = [
    "Division",
    "Team",
    "Player",
    "Match",
    "Club",
    "DivisionRepository",
    "TeamRepository",
    "PlayerRepository",
    "MatchRepository",
    "ClubRepository",
]


# -----------------------------
# Domain Dataclasses
# -----------------------------


@dataclass(frozen=True, slots=True)
class Division:
    id: str
    name: str
    level: Optional[str] = None  # e.g., Bezirksliga / Stadtliga
    category: Optional[str] = None  # Erwachsene / Jugend


@dataclass(frozen=True, slots=True)
class Club:
    id: str
    name: str


@dataclass(frozen=True, slots=True)
class Team:
    id: str
    name: str
    division_id: str
    club_id: Optional[str] = None


@dataclass(frozen=True, slots=True)
class Player:
    id: str
    name: str
    team_id: str
    live_pz: Optional[int] = None


@dataclass(frozen=True, slots=True)
class Match:
    id: str
    division_id: str
    home_team_id: str
    away_team_id: str
    iso_date: str  # YYYY-MM-DD
    round: Optional[int] = None
    home_score: Optional[int] = None
    away_score: Optional[int] = None


# -----------------------------
# Repository Protocols
# -----------------------------


@runtime_checkable
class DivisionRepository(Protocol):
    """Access divisions.

    Expected Query Patterns:
    - List all divisions (for navigation tree & ingestion loops)
    - Lookup by id
    """

    def list_divisions(self) -> Sequence[Division]: ...  # pragma: no cover - protocol

    def get_division(self, division_id: str) -> Division | None: ...  # pragma: no cover


@runtime_checkable
class TeamRepository(Protocol):
    """Access teams.

    Query patterns:
    - List by division for DivisionTableView
    - Lookup by id
    - List by club for Club detail aggregation
    """

    def list_teams_in_division(self, division_id: str) -> Sequence[Team]: ...  # pragma: no cover

    def get_team(self, team_id: str) -> Team | None: ...  # pragma: no cover

    def list_teams_for_club(self, club_id: str) -> Sequence[Team]: ...  # pragma: no cover


@runtime_checkable
class PlayerRepository(Protocol):
    """Access players.

    Query patterns:
    - Roster retrieval by team
    - Individual player stats lookup
    """

    def list_players_for_team(self, team_id: str) -> Sequence[Player]: ...  # pragma: no cover

    def get_player(self, player_id: str) -> Player | None: ...  # pragma: no cover


@runtime_checkable
class MatchRepository(Protocol):
    """Access matches.

    Query patterns:
    - Matches for team (past & future segmentation will be added later)
    - Matches for division (for schedule overview)
    """

    def list_matches_for_team(self, team_id: str) -> Sequence[Match]: ...  # pragma: no cover

    def list_matches_for_division(
        self, division_id: str
    ) -> Sequence[Match]: ...  # pragma: no cover

    def get_match(self, match_id: str) -> Match | None: ...  # pragma: no cover


@runtime_checkable
class ClubRepository(Protocol):
    """Access clubs and related teams."""

    def list_clubs(self) -> Sequence[Club]: ...  # pragma: no cover

    def get_club(self, club_id: str) -> Club | None: ...  # pragma: no cover


# Convenience aggregate type for injection contexts if needed later
class HasRepositories(Protocol):  # pragma: no cover - future convenience
    divisions: DivisionRepository
    teams: TeamRepository
    players: PlayerRepository
    matches: MatchRepository
    clubs: ClubRepository
