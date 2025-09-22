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
from gui.services.team_data_service import TeamDataService  # Milestone 5.9.6 integration
import os
import re
from tracking import tracking_store


class LandingLoadWorker(QThread):
    finished = pyqtSignal(list, str)  # teams, error

    def __init__(self, club_id: int, season: int):
        super().__init__()
        self.club_id = club_id
        self.season = season

    def run(self) -> None:  # type: ignore[override]
        """Load teams for landing view.

        Behavior change: Do NOT perform a live HTTP scrape automatically when
        no ingested data is present. Instead, emit empty list so the UI can
        prompt the user to run a full scrape. If ingested data exists (teams
        already in DB), load via repositories instead of remote fetch.
        """
        from gui.services.data_state_service import DataStateService
        from gui.repositories.sqlite_impl import create_sqlite_repositories
        from gui.services.service_locator import services as _services
        from gui.services.ingestion_coordinator import IngestionCoordinator
        from config import settings as _settings

        try:
            conn = _services.try_get("sqlite_conn")
            if conn is not None:
                # Check if we have ingested data
                state = DataStateService(conn).current_state()
                if state.has_data:
                    self.finished.emit(self._load_teams_from_db(conn), "")
                    return
                # Auto-ingest fallback: if DB empty but scraped HTML assets exist in data dir
                data_dir = getattr(_settings, "DATA_DIR", None)
                if data_dir and os.path.isdir(data_dir):
                    # Heuristic: presence of at least one ranking_table_*.html or team_roster_*.html
                    have_assets = False
                    for root, _, files in os.walk(data_dir):
                        for f in files:
                            if (
                                f.startswith("ranking_table_") or f.startswith("team_roster_")
                            ) and f.endswith(".html"):
                                have_assets = True
                                break
                        if have_assets:
                            break
                    if have_assets:
                        try:
                            coordinator = IngestionCoordinator(
                                base_dir=data_dir,
                                conn=conn,
                                event_bus=_services.try_get("event_bus"),
                            )
                            coordinator.run()
                            # Re-check state after ingest
                            state2 = DataStateService(conn).current_state()
                            if state2.has_data:
                                self.finished.emit(self._load_teams_from_db(conn), "")
                                return
                        except Exception as _e:  # pragma: no cover - debug fallback
                            # Swallow auto-ingest failure and fall through to empty state
                            import sys

                            print(f"[LandingLoadWorker] Auto-ingest failed: {_e}", file=sys.stderr)
            # If we reach here, no ingested data present: return empty (gate)
            # Fallback: attempt to load divisions from tracking JSON (non-ingested path) so tree is at least populated
            try:
                state = tracking_store.load_state()
                if state.divisions:
                    teams: list[TeamEntry] = []
                    for d in state.divisions.values():
                        for t in getattr(d, "teams", []):
                            # We do not yet persist club names in tracking JSON; keep None.
                            teams.append(
                                TeamEntry(
                                    team_id=t.id, name=t.name, division=d.name, club_name=None
                                )
                            )
                    teams.sort(key=lambda t: (t.division, t.display_name.lower()))
                    self.finished.emit(teams, "")
                    return
            except Exception:
                pass
            self.finished.emit([], "")
        except Exception:
            self.finished.emit([], traceback.format_exc())

    def _load_teams_from_db(self, conn):
        from gui.repositories.sqlite_impl import create_sqlite_repositories

        repos = create_sqlite_repositories(conn)
        # Pre-load clubs into dict for quick lookup
        club_map = {c.id: c.name for c in repos.clubs.list_clubs()}
        teams: list[TeamEntry] = []
        for d in repos.divisions.list_divisions():
            for t in repos.teams.list_teams_in_division(d.id):
                club_name = club_map.get(t.club_id) if getattr(t, "club_id", None) else None
                teams.append(
                    TeamEntry(team_id=t.id, name=t.name, division=d.name, club_name=club_name)
                )
        teams.sort(key=lambda t: (t.division, t.display_name.lower()))
        return teams


class RosterLoadWorker(QThread):
    finished = pyqtSignal(object, str)  # TeamRosterBundle, error

    def __init__(self, team: TeamEntry, season: int):
        super().__init__()
        self.team = team
        self.season = season

    def run(self) -> None:  # type: ignore[override]
        try:
            # Attempt repository-backed load first (ingested data path)
            try:
                svc = TeamDataService()
                repo_bundle = svc.load_team_bundle(self.team)
            except Exception:
                repo_bundle = None
            if repo_bundle is not None:
                self.finished.emit(repo_bundle, "")
                return
            # Build roster link heuristically; rely on ranking link derivation pattern
            # In future integrate stored links; for now attempt search in data dir if exists.
            data_dir = settings.DATA_DIR
            # Attempt find any roster file containing team name to reuse
            roster_html = None
            search_token = self.team.name.replace(" ", "_")
            for root, _, files in os.walk(data_dir):
                for f in files:
                    if f.startswith("team_roster_") and search_token in f:
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
