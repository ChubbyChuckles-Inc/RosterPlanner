"""Background worker threads for scraping tasks used by the GUI."""

from __future__ import annotations
from PyQt6.QtCore import QThread, pyqtSignal
from typing import List, Dict
import traceback
from config import settings
from parsing import link_extractor, ranking_parser, roster_parser
from scraping import ranking_scraper, roster_scraper
from core import filesystem
from utils import naming
from domain.models import Match, Player
from gui.models import TeamEntry, PlayerEntry, MatchDate, TeamRosterBundle
import os
import re


class LandingLoadWorker(QThread):
    finished = pyqtSignal(list, str)  # teams, error

    def __init__(self, club_id: int, season: int):
        super().__init__()
        self.club_id = club_id
        self.season = season

    def run(self) -> None:  # type: ignore[override]
        try:
            url = (
                "https://leipzig.tischtennislive.de/?L1=Public&L2=Verein&L2P="
                f"{self.club_id}&Page=Spielbetrieb&Sportart=96&Saison={self.season}"
            )
            html = ranking_scraper.http_client.fetch(url)  # type: ignore[attr-defined]
            teams_overview = ranking_parser.extract_team_overview(html)
            teams = [
                TeamEntry(team_id=t.id, name=t.name, division=t.division_name or "")
                for t in teams_overview.values()
            ]
            teams.sort(key=lambda t: (t.division, t.name))
            self.finished.emit(teams, "")
        except Exception:
            self.finished.emit([], traceback.format_exc())


class RosterLoadWorker(QThread):
    finished = pyqtSignal(object, str)  # TeamRosterBundle, error

    def __init__(self, team: TeamEntry, season: int):
        super().__init__()
        self.team = team
        self.season = season

    def run(self) -> None:  # type: ignore[override]
        try:
            # Build roster link heuristically; rely on ranking link derivation pattern
            # In future integrate stored links; for now attempt search in data dir if exists.
            data_dir = settings.DATA_DIR
            # Attempt find any roster file containing team name to reuse
            roster_html = None
            for root, _, files in os.walk(data_dir):
                for f in files:
                    if f.startswith("team_roster_") and self.team.name.replace(" ", "_") in f:
                        roster_html = filesystem.read_text(os.path.join(root, f))
                        break
                if roster_html:
                    break
            if roster_html is None:
                # Fallback: require prior full scrape or skip
                self.finished.emit(
                    TeamRosterBundle(team=self.team, players=[], match_dates=[]),
                    f"Roster HTML not found for team {self.team.name}. Run full scrape first.",
                )
                return
            players_raw = roster_parser.extract_players(roster_html, team_id=self.team.team_id)
            matches_raw = roster_parser.extract_matches(roster_html, team_id=self.team.team_id)
            players = [
                PlayerEntry(team_id=self.team.team_id, name=p.name, live_pz=p.live_pz)
                for p in players_raw
            ]
            # Build unique match date list
            date_map = {}
            for m in matches_raw:
                if m.date:
                    iso = _to_iso(m.date)
                    if iso not in date_map:
                        date_map[iso] = MatchDate(iso_date=iso, display=m.date, time=m.time)
            bundle = TeamRosterBundle(
                team=self.team, players=players, match_dates=list(date_map.values())
            )
            self.finished.emit(bundle, "")
        except Exception:
            self.finished.emit(
                TeamRosterBundle(team=self.team, players=[], match_dates=[]), traceback.format_exc()
            )


def _to_iso(date_str: str) -> str:
    # Expect format DD.MM.YYYY
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", date_str)
    if not m:
        return date_str
    d, mo, y = m.groups()
    return f"{y}-{mo}-{d}"
