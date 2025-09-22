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


def run_basic(club_id: int, season: int | None = None, data_dir: str | None = None) -> dict:
    """Run lightweight discovery only scrape.

    data_dir is optional (used only for reading tracking state); defaults to settings.DATA_DIR.
    """
    season = season or settings.DEFAULT_SEASON
    target_dir = data_dir or settings.DATA_DIR
    url = LANDING_URL_TEMPLATE.format(club_id=club_id, season=season)
    html = ranking_scraper.http_client.fetch(url)  # type: ignore[attr-defined]
    roster_links = link_extractor.extract_team_roster_links(html)
    ranking_links = link_extractor.derive_ranking_table_links(roster_links)
    teams_overview = ranking_scraper.fetch_and_parse_overview(url)
    state = tracking_store.load_state(target_dir)
    return {
        "landing_url": url,
        "team_roster_links_found": len(roster_links),
        "ranking_table_links_found": len(ranking_links),
        "teams_discovered": len(teams_overview),
        "tracking_last_scrape": state.last_scrape.isoformat() if state.last_scrape else None,
    }


def run_full(club_id: int, season: int | None = None, data_dir: str | None = None) -> dict:
    """Run full scrape pipeline writing HTML assets to data_dir (or default)."""
    season = season or settings.DEFAULT_SEASON
    data_dir = data_dir or settings.DATA_DIR
    os.makedirs(data_dir, exist_ok=True)
    landing_url = LANDING_URL_TEMPLATE.format(club_id=club_id, season=season)

    # Step 1: Landing page fetch & initial extraction
    landing_html = ranking_scraper.http_client.fetch(landing_url)  # type: ignore[attr-defined]
    # Snapshot archive of landing page for parity (timestamped)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    snapshot_name = f"website_source_{timestamp}.html"
    filesystem.write_text(os.path.join(data_dir, snapshot_name), landing_html)
    initial_roster_links = link_extractor.extract_team_roster_links(landing_html)
    ranking_links = link_extractor.derive_ranking_table_links(initial_roster_links)
    teams_overview = ranking_parser.extract_team_overview(landing_html)

    # Step 2: Fetch ranking tables & parse for division roster lists
    division_team_lists: dict[str, list[dict]] = {}
    for idx, rlink in enumerate(ranking_links, start=1):
        # Fetch ranking table HTML directly (do not persist with generic name first)
        ranking_html = ranking_scraper.http_client.fetch(rlink)  # type: ignore[attr-defined]
        division_name, teams = ranking_parser.parse_ranking_table(
            ranking_html, source_hint=f"division_{idx}"
        )
        # Persist under division directory using real division name
        div_dir = os.path.join(data_dir, naming.sanitize(division_name))
        os.makedirs(div_dir, exist_ok=True)
        ranking_filename = naming.ranking_table_filename(division_name)
        filesystem.write_text(os.path.join(div_dir, ranking_filename), ranking_html)
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
            # Ensure division dir
            div_dir = os.path.join(data_dir, naming.sanitize(division_name))
            os.makedirs(div_dir, exist_ok=True)
            path = roster_scraper.fetch_roster(
                full_url, division_name, team["team_name"], team_id, div_dir
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
    # Additionally, include any club ids derivable from teams_overview (ensures broader coverage than only roster-derived links)
    club_extra_teams: dict[str, Team] = {}
    discovered_club_ids = set(club_links.keys())
    # Attempt to derive club ids from teams_overview Team objects (they may already have club_id populated)
    for t in teams_overview.values():  # type: ignore[attr-defined]
        if getattr(t, "club_id", None):
            discovered_club_ids.add(t.club_id)  # type: ignore[attr-defined]

    club_id_to_name: dict[str, str] = {}
    # Always ensure the primary club_id requested is included even if not discovered via roster links yet
    discovered_club_ids.add(str(club_id))
    for club_id_key in sorted(discovered_club_ids):
        # If we already have a full club link use it; otherwise synthesize typical pattern (landing Verein page)
        club_link = club_links.get(club_id_key)
        if club_link:
            full_url = (
                club_link if club_link.startswith("http") else f"{settings.ROOT_URL}{club_link}"
            )
        else:
            # Synthesize landing Verein page for the given season
            full_url = LANDING_URL_TEMPLATE.format(club_id=club_id_key, season=season)
        try:
            club_name, teams = club_scraper.fetch_and_parse_club(full_url, club_id_key, data_dir)
            if club_name:
                club_id_to_name[club_id_key] = club_name
        except Exception:
            continue
        for tid, t in teams.items():
            club_extra_teams[tid] = t

    # Step 6: Merge teams (base + club extras)
    merged_teams = domain_mapping.merge_team_club_data(teams_overview, club_extra_teams)

    # Step 7: Build upcoming matches
    upcoming = upcoming_matches.build_upcoming(all_matches, merged_teams)

    # Step 7b: Fetch club team detail pages (parity with legacy dataset)
    club_team_dir = os.path.join(data_dir, "club_teams")
    os.makedirs(club_team_dir, exist_ok=True)
    for team_id, team in club_extra_teams.items():
        # Construct roster detail URL using known template; if division id (L2P) is unknown leave blank
        roster_url = club_parser.build_roster_link(team_id)
        full_url = (
            roster_url if roster_url.startswith("http") else f"{settings.ROOT_URL}{roster_url}"
        )
        try:
            html = ranking_scraper.http_client.fetch(full_url)  # type: ignore[attr-defined]
        except Exception:
            continue
        # Determine club display name (prefer mapped name by original numeric id; team.club_id may already be name if patched)
        raw_club_ref = getattr(team, "club_id", "unknown_club") or "unknown_club"
        club_display = club_id_to_name.get(raw_club_ref, raw_club_ref)
        # If raw_club_ref still looks numeric and we have a mapping for its numeric form use that
        if raw_club_ref.isdigit() and raw_club_ref in club_id_to_name:
            club_display = club_id_to_name[raw_club_ref]
        # Use name-based filename utility
        fname = naming.club_team_by_name_filename(club_display, team.name, team.id)
        filesystem.write_text(os.path.join(club_team_dir, fname), html)

    # Step 7c: Generate flat team_rosters/ team_roster_L2P_<id>.html pages (legacy parity)
    flat_team_roster_dir = os.path.join(data_dir, "team_rosters")
    os.makedirs(flat_team_roster_dir, exist_ok=True)
    produced_flat_ids: set[str] = set()
    # Reconstruct from division_team_lists first
    import re as _re

    for division_name, teams in division_team_lists.items():
        for t in teams:
            m = _re.search(r"L3P=(\d+)", t.get("roster_link", ""))
            if m:
                tid = m.group(1)
                if tid in produced_flat_ids:
                    continue
                url = club_parser.build_roster_link(tid)
                full_url = url if url.startswith("http") else f"{settings.ROOT_URL}{url}"
                try:
                    html = ranking_scraper.http_client.fetch(full_url)  # type: ignore[attr-defined]
                except Exception:
                    continue
                filesystem.write_text(
                    os.path.join(flat_team_roster_dir, f"team_roster_L2P_{tid}.html"), html
                )
                produced_flat_ids.add(tid)
    # Include extra club teams not already in division list
    for tid, team in club_extra_teams.items():
        if tid in produced_flat_ids:
            continue
        url = club_parser.build_roster_link(tid)
        full_url = url if url.startswith("http") else f"{settings.ROOT_URL}{url}"
        try:
            html = ranking_scraper.http_client.fetch(full_url)  # type: ignore[attr-defined]
        except Exception:
            continue
        filesystem.write_text(
            os.path.join(flat_team_roster_dir, f"team_roster_L2P_{tid}.html"), html
        )
        produced_flat_ids.add(tid)

    # Step 7d (rewritten): Deterministic primary club backfill ensuring BOTH club_team_* and division-style team_roster_* files
    # Rationale: Earlier logic attempted to infer primary club teams from merged extras; this could fail in heavily mocked
    # test environments where team.club_id mutation differs. We now always (re)fetch the primary club overview explicitly.
    try:
        primary_club_url = LANDING_URL_TEMPLATE.format(club_id=club_id, season=season)
        primary_name, primary_teams = club_scraper.fetch_and_parse_club(
            primary_club_url, str(club_id), data_dir
        )
        if primary_name:
            club_id_to_name[str(club_id)] = primary_name
    except Exception:  # pragma: no cover - defensive
        primary_name, primary_teams = None, {}

    # Existing file inventories
    club_team_dir = os.path.join(data_dir, "club_teams")
    os.makedirs(club_team_dir, exist_ok=True)
    existing_club_team_files = set(os.listdir(club_team_dir))
    existing_division_rosters: set[str] = set()
    for root, dirs, files in os.walk(data_dir):  # pragma: no cover - traversal
        for f in files:
            if f.startswith("team_roster_") and f.endswith(".html"):
                existing_division_rosters.add(f)

    for tid, t in primary_teams.items():
        # Determine display club name preference order: explicit primary_name -> mapped name -> numeric id fallback
        club_display = primary_name or club_id_to_name.get(str(club_id)) or str(club_id)
        # 1. club_team_*
        club_team_filename = naming.club_team_by_name_filename(club_display, t.name, t.id)
        if club_team_filename not in existing_club_team_files:
            roster_url = club_parser.build_roster_link(tid)
            full_url = (
                roster_url if roster_url.startswith("http") else f"{settings.ROOT_URL}{roster_url}"
            )
            try:
                html = ranking_scraper.http_client.fetch(full_url)  # type: ignore[attr-defined]
                filesystem.write_text(os.path.join(club_team_dir, club_team_filename), html)
                existing_club_team_files.add(club_team_filename)
            except Exception:  # pragma: no cover - network/parse resilience
                pass
        # 2. division-style team_roster_<division>_... (fallback 'unknown_division' if absent)
        div_name = getattr(t, "division_name", None) or "unknown_division"
        div_dir = os.path.join(data_dir, naming.sanitize(div_name))
        os.makedirs(div_dir, exist_ok=True)
        roster_filename = naming.team_roster_filename(div_name, t.name, t.id)
        if roster_filename not in existing_division_rosters:
            roster_url = club_parser.build_roster_link(tid)
            full_url = (
                roster_url if roster_url.startswith("http") else f"{settings.ROOT_URL}{roster_url}"
            )
            try:
                html = ranking_scraper.http_client.fetch(full_url)  # type: ignore[attr-defined]
                filesystem.write_text(os.path.join(div_dir, roster_filename), html)
                existing_division_rosters.add(roster_filename)
            except Exception:  # pragma: no cover
                pass

    # Step 8: Persist tracking state
    state = TrackingState(last_scrape=datetime.utcnow(), divisions={}, upcoming_matches=upcoming)
    tracking_store.save_state(state, data_dir)

    return {
        "landing_url": landing_url,
        "divisions_discovered": len(division_team_lists),
        "teams_overview": len(teams_overview),
        "club_extra_teams": len(club_extra_teams),
        "club_team_pages": len(club_extra_teams),
        "club_name_mappings": len(club_id_to_name),
        "total_matches": sum(len(v) for v in all_matches.values()),
        "upcoming_matches": len(upcoming),
        "players_total": sum(len(v) for v in all_players.values()),
        "tracking_saved": True,
        "output_dir": data_dir,
    }
