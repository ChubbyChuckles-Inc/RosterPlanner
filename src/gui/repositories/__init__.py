"""Repository layer public exports (Milestones 5.9.1 - 5.9.2).

Exposes Protocol interfaces, domain dataclasses, and SQLite-backed
implementations used across GUI services and upcoming ingestion coordinator.
"""

from .protocols import (
    Division,
    Team,
    Player,
    Match,
    Club,
    DivisionRepository,
    TeamRepository,
    PlayerRepository,
    MatchRepository,
    ClubRepository,
)
from .sqlite_impl import (
    SqliteDivisionRepository,
    SqliteTeamRepository,
    SqlitePlayerRepository,
    SqliteMatchRepository,
    SqliteClubRepository,
    create_sqlite_repositories,
    SqliteRepositories,
)

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
    "SqliteDivisionRepository",
    "SqliteTeamRepository",
    "SqlitePlayerRepository",
    "SqliteMatchRepository",
    "SqliteClubRepository",
    "SqliteRepositories",
    "create_sqlite_repositories",
]
