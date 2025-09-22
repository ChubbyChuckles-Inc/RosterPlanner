"""Tests for repository protocol layer (Milestone 5.9.1).

These tests validate that simple in-memory stub implementations satisfy the
Protocol contracts and demonstrate expected query behavior. While Protocols
are structural, runtime `isinstance` checks are used via `runtime_checkable`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

from gui.repositories import (
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


# ------------------ Stub Implementations ------------------


@dataclass
class _Data:
    divisions: List[Division]
    clubs: List[Club]
    teams: List[Team]
    players: List[Player]
    matches: List[Match]


class InMemoryDivisionRepo(DivisionRepository):  # type: ignore[misc]
    def __init__(self, data: _Data) -> None:
        self._data = data

    def list_divisions(self) -> Sequence[Division]:
        return list(self._data.divisions)

    def get_division(self, division_id: str) -> Division | None:
        return next((d for d in self._data.divisions if d.id == division_id), None)


class InMemoryTeamRepo(TeamRepository):  # type: ignore[misc]
    def __init__(self, data: _Data) -> None:
        self._data = data

    def list_teams_in_division(self, division_id: str) -> Sequence[Team]:
        return [t for t in self._data.teams if t.division_id == division_id]

    def get_team(self, team_id: str) -> Team | None:
        return next((t for t in self._data.teams if t.id == team_id), None)

    def list_teams_for_club(self, club_id: str) -> Sequence[Team]:
        return [t for t in self._data.teams if t.club_id == club_id]


class InMemoryPlayerRepo(PlayerRepository):  # type: ignore[misc]
    def __init__(self, data: _Data) -> None:
        self._data = data

    def list_players_for_team(self, team_id: str) -> Sequence[Player]:
        return [p for p in self._data.players if p.team_id == team_id]

    def get_player(self, player_id: str) -> Player | None:
        return next((p for p in self._data.players if p.id == player_id), None)


class InMemoryMatchRepo(MatchRepository):  # type: ignore[misc]
    def __init__(self, data: _Data) -> None:
        self._data = data

    def list_matches_for_team(self, team_id: str):  # Sequence[Match]
        return [
            m for m in self._data.matches if m.home_team_id == team_id or m.away_team_id == team_id
        ]

    def list_matches_for_division(self, division_id: str):  # Sequence[Match]
        return [m for m in self._data.matches if m.division_id == division_id]

    def get_match(self, match_id: str) -> Match | None:
        return next((m for m in self._data.matches if m.id == match_id), None)


class InMemoryClubRepo(ClubRepository):  # type: ignore[misc]
    def __init__(self, data: _Data) -> None:
        self._data = data

    def list_clubs(self) -> Sequence[Club]:
        return list(self._data.clubs)

    def get_club(self, club_id: str) -> Club | None:
        return next((c for c in self._data.clubs if c.id == club_id), None)


# ------------------ Tests ------------------


def _sample_data() -> _Data:
    div = Division(id="d1", name="1. Stadtliga Gruppe 1", level="Stadtliga", category="Erwachsene")
    club = Club(id="c1", name="LTTV Leutzscher Füchse 1990")
    team_a = Team(id="t1", name="Füchse 1", division_id="d1", club_id="c1")
    team_b = Team(id="t2", name="Füchse 2", division_id="d1", club_id="c1")
    player_1 = Player(id="p1", name="Alice", team_id="t1", live_pz=1500)
    player_2 = Player(id="p2", name="Bob", team_id="t1", live_pz=1480)
    player_3 = Player(id="p3", name="Cara", team_id="t2", live_pz=1490)
    match_1 = Match(
        id="m1", division_id="d1", home_team_id="t1", away_team_id="t2", iso_date="2025-09-21"
    )
    return _Data(
        divisions=[div],
        clubs=[club],
        teams=[team_a, team_b],
        players=[player_1, player_2, player_3],
        matches=[match_1],
    )


def test_protocol_isinstance_and_queries():
    data = _sample_data()
    div_repo = InMemoryDivisionRepo(data)
    team_repo = InMemoryTeamRepo(data)
    player_repo = InMemoryPlayerRepo(data)
    match_repo = InMemoryMatchRepo(data)
    club_repo = InMemoryClubRepo(data)

    # Protocol runtime checks
    assert isinstance(div_repo, DivisionRepository)
    assert isinstance(team_repo, TeamRepository)
    assert isinstance(player_repo, PlayerRepository)
    assert isinstance(match_repo, MatchRepository)
    assert isinstance(club_repo, ClubRepository)

    # Division queries
    divisions = div_repo.list_divisions()
    assert len(divisions) == 1 and divisions[0].id == "d1"
    assert div_repo.get_division("d1").name.startswith("1. Stadtliga")

    # Team queries
    teams_div = team_repo.list_teams_in_division("d1")
    assert {t.id for t in teams_div} == {"t1", "t2"}
    assert team_repo.get_team("t1").name == "Füchse 1"
    assert len(team_repo.list_teams_for_club("c1")) == 2

    # Player queries
    roster = player_repo.list_players_for_team("t1")
    assert {p.id for p in roster} == {"p1", "p2"}
    assert player_repo.get_player("p3").name == "Cara"

    # Match queries
    matches_team = match_repo.list_matches_for_team("t1")
    assert len(matches_team) == 1 and matches_team[0].id == "m1"
    assert match_repo.get_match("m1").away_team_id == "t2"

    # Club queries
    clubs = club_repo.list_clubs()
    assert len(clubs) == 1 and clubs[0].id == "c1"
    assert club_repo.get_club("c1").name.startswith("LTTV")
