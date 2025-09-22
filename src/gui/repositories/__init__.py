"""Repository layer public exports (Milestone 5.9.1).

Exposes Protocol interfaces and domain dataclasses used across GUI
services and future ingestion coordinator logic.
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
