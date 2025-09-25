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
from domain.models import Team, Match, Player, TrackingState, Division
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
    # Map team_id -> division_id (distinct) gathered from ranking tables for later repair of legacy incorrect files
    team_division_map: dict[str, str] = {}
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
        for t in teams:
            tid = t.get("team_id") or None
            did = t.get("division_id") or None
            if tid and did and tid != did:
                team_division_map[tid] = did

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
            # Division id (L2P) distinct from team id
            m_div = re.search(r"L2P=(\d+)", roster_link)
            division_id = m_div.group(1) if m_div else None
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
        roster_url = club_parser.build_roster_link(team_id, getattr(team, "division_id", None))
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

    # Step 7b.1: Player history pages scraping (new)
    # For each saved club team HTML, parse player profile links and fetch their history (EntwicklungTTR page).
    player_history_root = os.path.join(data_dir, "club_players")
    os.makedirs(player_history_root, exist_ok=True)
    import re as _re_history
    from html import unescape as _unescape

    def _extract_player_links(html: str):
        # Matches anchor tags with Spieler profile (L3=Spieler & L3P=<id>) capturing href and visible name
        pattern = _re_history.compile(r'<a\s+href="(\?L1=[^"]*?L3=Spieler&L3P=\d+[^"#>]*)"[^>]*>(.*?)</a>', re.IGNORECASE)
        results = []
        for m in pattern.finditer(html):
            href = m.group(1)
            name_raw = m.group(2)
            # Strip HTML entities & tags inside name if any
            name_txt = _re_history.sub(r"<[^>]+>", "", _unescape(name_raw)).strip()
            if not name_txt:
                continue
            results.append((href, name_txt))
        return results

    for team_html_name in os.listdir(club_team_dir):
        if not team_html_name.startswith("club_team_") or not team_html_name.endswith(".html"):
            continue
        # Derive subfolder name: strip prefix 'club_team_' and trailing '_<id>.html'
        base = team_html_name[len("club_team_") : -5]  # remove prefix and .html
        # Remove the trailing _<digits> (team id) to form folder name
        folder = _re_history.sub(r"_\d+$", "", base)
        if not folder:
            continue
        folder_path = os.path.join(player_history_root, folder)
        os.makedirs(folder_path, exist_ok=True)
        team_html = filesystem.read_text(os.path.join(club_team_dir, team_html_name))
        links = _extract_player_links(team_html)
        for rel_link, player_name in links:
            # Build history URL by replacing Page=Vorrunde (or any Page=...) with Page=EntwicklungTTR
            if "Page=" in rel_link:
                rel_history = _re_history.sub(r"Page=[A-Za-z0-9]+", "Page=EntwicklungTTR", rel_link)
            else:
                # Append if missing
                sep = '&' if rel_link.endswith('&') or '?' in rel_link else '&'
                rel_history = f"{rel_link}{sep}Page=EntwicklungTTR"
            history_url = rel_history if rel_history.startswith("http") else f"{settings.ROOT_URL}{rel_history}"
            safe_player = naming.sanitize(player_name.replace(" ", "_"))
            out_path = os.path.join(folder_path, f"{safe_player}.html")
            if os.path.exists(out_path):  # skip existing to avoid refetch noise
                continue
            try:
                hist_html = ranking_scraper.http_client.fetch(history_url)  # type: ignore[attr-defined]
                filesystem.write_text(out_path, hist_html)
            except Exception:
                continue

    # Step 7c (updated): Deterministic primary club backfill ensuring club_team_* files exist.
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
            roster_url = club_parser.build_roster_link(tid, getattr(t, "division_id", None))
            full_url = (
                roster_url if roster_url.startswith("http") else f"{settings.ROOT_URL}{roster_url}"
            )
            try:
                html = ranking_scraper.http_client.fetch(full_url)  # type: ignore[attr-defined]
                # Fallback: if player anchors missing, attempt alternate page variants
                if "?L1=" in full_url and "Page=Vorrunde" in full_url and "Spieler" not in html:
                    for alt in ("Gesamt", "Rueckrunde"):
                        alt_url = full_url.replace("Page=Vorrunde", f"Page={alt}")
                        try:
                            alt_html = ranking_scraper.http_client.fetch(alt_url)  # type: ignore[attr-defined]
                            if "Spieler" in alt_html:
                                html = alt_html
                                break
                        except Exception:
                            continue
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
            roster_url = club_parser.build_roster_link(tid, getattr(t, "division_id", None))
            full_url = (
                roster_url if roster_url.startswith("http") else f"{settings.ROOT_URL}{roster_url}"
            )
            try:
                html = ranking_scraper.http_client.fetch(full_url)  # type: ignore[attr-defined]
                if "?L1=" in full_url and "Page=Vorrunde" in full_url and "Spieler" not in html:
                    for alt in ("Gesamt", "Rueckrunde"):
                        alt_url = full_url.replace("Page=Vorrunde", f"Page={alt}")
                        try:
                            alt_html = ranking_scraper.http_client.fetch(alt_url)  # type: ignore[attr-defined]
                            if "Spieler" in alt_html:
                                html = alt_html
                                break
                        except Exception:
                            continue
                filesystem.write_text(os.path.join(div_dir, roster_filename), html)
                existing_division_rosters.add(roster_filename)
            except Exception:  # pragma: no cover
                pass

    # Step 7d: Repair previously fetched incorrect roster files where L2P (division) and L3P (team) were the same
    # (Only when we have a distinct division id captured for that team.)
    for team_id, division_id in team_division_map.items():
        if team_id == division_id:
            continue
        # Look for roster files ending with this team id
        for root_dir, _dirs, files in os.walk(data_dir):
            for f in files:
                if not f.startswith("team_roster_") or not f.endswith(f"_{team_id}.html"):
                    continue
                fpath = os.path.join(root_dir, f)
                try:
                    html_existing = filesystem.read_text(fpath)
                except Exception:
                    continue
                # If already correct (contains distinct division id) skip
                if f"L2P={division_id}" in html_existing and f"L3P={team_id}" in html_existing:
                    continue
                # If shows legacy duplicated pattern attempt refetch
                if f"L2P={team_id}" in html_existing and f"L3P={team_id}" in html_existing:
                    try:
                        repair_url = club_parser.build_roster_link(team_id, division_id)
                        full_url = (
                            repair_url
                            if repair_url.startswith("http")
                            else f"{settings.ROOT_URL}{repair_url}"
                        )
                        new_html = ranking_scraper.http_client.fetch(full_url)  # type: ignore[attr-defined]
                        # Fallback to alternate pages if still missing players
                        if "Spieler" not in new_html and "Page=Vorrunde" in full_url:
                            for alt in ("Gesamt", "Rueckrunde"):
                                alt_url = full_url.replace("Page=Vorrunde", f"Page={alt}")
                                try:
                                    alt_html = ranking_scraper.http_client.fetch(alt_url)  # type: ignore[attr-defined]
                                    if "Spieler" in alt_html:
                                        new_html = alt_html
                                        break
                                except Exception:
                                    continue
                        filesystem.write_text(fpath, new_html)
                    except Exception:
                        continue

    # Step 8: Build divisions structure for tracking state (used by GUI tree) and persist
    divisions_map: dict[str, Division] = {}
    for team in merged_teams.values():
        div_name = team.division_name or "Unknown_Division"
        if div_name not in divisions_map:
            divisions_map[div_name] = Division(name=div_name, teams=[])
        divisions_map[div_name].teams.append(team)
    # Sort teams in each division for deterministic UI ordering
    for d in divisions_map.values():
        d.teams.sort(key=lambda t: t.name)

    state = TrackingState(
        last_scrape=datetime.utcnow(), divisions=divisions_map, upcoming_matches=upcoming
    )
    tracking_store.save_state(state, data_dir)

    return {
        "landing_url": landing_url,
        "divisions_discovered": len(divisions_map),
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
