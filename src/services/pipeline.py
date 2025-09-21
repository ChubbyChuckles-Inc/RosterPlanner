"""High-level orchestration pipeline (extended)."""

from __future__ import annotations
from typing import Dict, List
from datetime import datetime
import os

from config import settings
from scraping import ranking_scraper, roster_scraper, club_scraper
from parsing import link_extractor, ranking_parser, roster_parser, club_parser
from core import filesystem
from utils import naming
from domain.models import Team, Match, Player, TrackingState
from domain import mapping as domain_mapping
from tracking import tracking_store, rescrape_policy, upcoming_matches


LANDING_URL_TEMPLATE = (
    "https://leipzig.tischtennislive.de/"
    "?L1=Public&L2=Verein&L2P={club_id}&Page=Spielbetrieb&Sportart=96&Saison={season}"
)


def run_basic(club_id: int, season: int | None = None) -> dict:
    season = season or settings.DEFAULT_SEASON
    url = LANDING_URL_TEMPLATE.format(club_id=club_id, season=season)
    html = ranking_scraper.http_client.fetch(url)  # type: ignore[attr-defined]
    roster_links = link_extractor.extract_team_roster_links(html)
    ranking_links = link_extractor.derive_ranking_table_links(roster_links)
    teams_overview = ranking_scraper.fetch_and_parse_overview(url)
    state = tracking_store.load_state(settings.DATA_DIR)
    return {
        "landing_url": url,
        "team_roster_links_found": len(roster_links),
        "ranking_table_links_found": len(ranking_links),
        "teams_discovered": len(teams_overview),
        "tracking_last_scrape": state.last_scrape.isoformat() if state.last_scrape else None,
    }


def run_full(club_id: int, season: int | None = None) -> dict:
    season = season or settings.DEFAULT_SEASON
    data_dir = settings.DATA_DIR
    os.makedirs(data_dir, exist_ok=True)
    landing_url = LANDING_URL_TEMPLATE.format(club_id=club_id, season=season)

    # Step 1: Landing page fetch & initial extraction
    landing_html = ranking_scraper.http_client.fetch(landing_url)  # type: ignore[attr-defined]
    initial_roster_links = link_extractor.extract_team_roster_links(landing_html)
    ranking_links = link_extractor.derive_ranking_table_links(initial_roster_links)
    teams_overview = ranking_parser.extract_team_overview(landing_html)

    # Step 2: Fetch ranking tables & parse for division roster lists
    division_files: list[str] = []
    division_team_lists: dict[str, list[dict]] = {}
    for rlink in ranking_links:
        # Attempt derive division id/name from URL or fallback index
        div_id_match = None
        # Use simple incremental index if no better name
        division_hint = f"division_{len(division_files)+1}"
        path = ranking_scraper.fetch_ranking_table(rlink, division_hint, data_dir)
        division_files.append(path)
        html = filesystem.read_text(path)
        division_name, teams = ranking_parser.parse_ranking_table(html, os.path.basename(path))
        division_team_lists[division_name] = teams

    # Step 3: Fetch rosters for each team in divisions
    all_matches: dict[str, list[Match]] = {}
    all_players: dict[str, list[Player]] = {}

    for division_name, teams in division_team_lists.items():
        for team in teams:
            roster_link = team["roster_link"]
            full_url = (
                roster_link
                if roster_link.startswith("http")
                else f"{settings.ROOT_URL}{roster_link}"
            )
            # Extract team id from link
            team_id_match = None
            import re

            m = re.search(r"L3P=(\d+)", roster_link)
            team_id = m.group(1) if m else f"unknown_{team['team_name']}"
            path = roster_scraper.fetch_roster(
                full_url, division_name, team["team_name"], team_id, data_dir
            )
            roster_html = filesystem.read_text(path)
            matches = roster_parser.extract_matches(roster_html, team_id=team_id)
            players = roster_parser.extract_players(roster_html, team_id=team_id)
            all_matches[team_id] = matches
            all_players[team_id] = players

    # Step 4: Extract club links from rosters
    club_links: dict[str, str] = {}
    for division_name in os.listdir(data_dir):
        div_path = os.path.join(data_dir, division_name)
        if not os.path.isdir(div_path):
            continue
        for fname in os.listdir(div_path):
            if fname.startswith("team_roster_") and fname.endswith(".html"):
                html = filesystem.read_text(os.path.join(div_path, fname))
                link = roster_parser.extract_club_link(html)
                if link:
                    import re

                    cid_match = re.search(r"L2P=([^&]+)", link)
                    if cid_match:
                        club_links[cid_match.group(1)] = link

    # Step 5: Fetch club overviews & extract additional teams
    club_extra_teams: dict[str, Team] = {}
    for club_id_key, club_link in club_links.items():
        full_url = club_link if club_link.startswith("http") else f"{settings.ROOT_URL}{club_link}"
        teams = club_scraper.fetch_and_parse_club(full_url, club_id_key, data_dir)
        for tid, t in teams.items():
            club_extra_teams[tid] = t

    # Step 6: Merge teams (base + club extras)
    merged_teams = domain_mapping.merge_team_club_data(teams_overview, club_extra_teams)

    # Step 7: Build upcoming matches
    upcoming = upcoming_matches.build_upcoming(all_matches, merged_teams)

    # Step 8: Persist tracking state
    state = TrackingState(last_scrape=datetime.utcnow(), divisions={}, upcoming_matches=upcoming)
    tracking_store.save_state(state, data_dir)

    return {
        "landing_url": landing_url,
        "divisions_discovered": len(division_team_lists),
        "teams_overview": len(teams_overview),
        "club_extra_teams": len(club_extra_teams),
        "total_matches": sum(len(v) for v in all_matches.values()),
        "upcoming_matches": len(upcoming),
        "players_total": sum(len(v) for v in all_players.values()),
        "tracking_saved": True,
    }
