"""ClubDataService (Milestone 5.9.8)

Aggregates club-level statistics from ingested data via repository protocols.
Current metrics:
 - Team counts per division
 - Erwachsene vs Jugend split
 - Average LivePZ across all players (ignoring NULLs)

Design: Pull repositories from service locator to avoid tight coupling.
Falls back gracefully if repositories are missing (empty stats returned).
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Optional

from gui.repositories.protocols import TeamRepository, PlayerRepository
from gui.services.service_locator import services

__all__ = [
    "ClubTeamSummary",
    "ClubAggregateStats",
    "ClubDataService",
]


@dataclass(frozen=True)
class ClubTeamSummary:
    division: str
    team_count: int
    classification: str  # Erwachsene / Jugend


@dataclass(frozen=True)
class ClubAggregateStats:
    club_id: str
    teams: List[ClubTeamSummary]
    total_teams: int
    erwachsene_teams: int
    jugend_teams: int
    avg_live_pz: Optional[float]
    active_teams: int
    inactive_teams: int

    def as_dict(self) -> dict:
        return {
            "club_id": self.club_id,
            "total_teams": self.total_teams,
            "erwachsene": self.erwachsene_teams,
            "jugend": self.jugend_teams,
            "avg_live_pz": self.avg_live_pz,
            "active_teams": self.active_teams,
            "inactive_teams": self.inactive_teams,
            "divisions": [
                {
                    "division": t.division,
                    "teams": t.team_count,
                    "type": t.classification,
                }
                for t in self.teams
            ],
        }


class ClubDataService:
    def __init__(
        self, teams: TeamRepository | None = None, players: PlayerRepository | None = None
    ):
        self._teams = teams or services.try_get("teams_repo")  # type: ignore[assignment]
        self._players = players or services.try_get("players_repo")  # type: ignore[assignment]

    def load_club_stats(self, club_id: str) -> ClubAggregateStats:
        if not self._teams:
            return ClubAggregateStats(club_id, [], 0, 0, 0, None)
        try:
            club_teams = list(self._teams.list_teams_for_club(club_id))  # type: ignore[attr-defined]
        except Exception:
            club_teams = []
        by_div: Dict[str, list] = {}
        erw = jug = 0
        for t in club_teams:
            div_name = getattr(t, "division_id", "") or getattr(t, "division", "")
            classification = "Jugend" if "Jugend" in div_name else "Erwachsene"
            if classification == "Jugend":
                jug += 1
            else:
                erw += 1
            by_div.setdefault(div_name, []).append(t)
        summaries: List[ClubTeamSummary] = [
            ClubTeamSummary(
                division=d,
                team_count=len(v),
                classification=("Jugend" if "Jugend" in d else "Erwachsene"),
            )
            for d, v in sorted(by_div.items())
        ]
        avg_live_pz: Optional[float] = None
        active_teams = inactive_teams = 0
        if self._players and club_teams:
            live_values: list[int] = []
            for t in club_teams:
                try:
                    plist = self._players.list_players_for_team(t.id)  # type: ignore[attr-defined]
                except Exception:
                    continue
                if plist:
                    active_teams += 1
                else:
                    inactive_teams += 1
                for p in plist:
                    lpz = getattr(p, "live_pz", None)
                    if isinstance(lpz, int):
                        live_values.append(lpz)
            if live_values:
                avg_live_pz = sum(live_values) / len(live_values)
        else:
            # Without player repo we can't classify active/inactive; treat as unknown -> all inactive = 0 active
            active_teams = 0
            inactive_teams = 0 if not club_teams else 0
        return ClubAggregateStats(
            club_id=club_id,
            teams=summaries,
            total_teams=len(club_teams),
            erwachsene_teams=erw,
            jugend_teams=jug,
            avg_live_pz=avg_live_pz,
            active_teams=active_teams,
            inactive_teams=inactive_teams,
        )
