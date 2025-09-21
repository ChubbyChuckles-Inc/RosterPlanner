from pathlib import Path
from parsing import ranking_parser, roster_parser, link_extractor

DATA_DIR = Path("data")


def read_sample(name_substring: str) -> str:
    for p in DATA_DIR.rglob("*.html"):
        if name_substring in p.name:
            return p.read_text(encoding="utf-8")
    raise RuntimeError(f"Sample {name_substring} not found")


def test_link_extraction_from_main_page():
    # Use first website_source file as landing page sample
    html = read_sample("website_source_")
    roster_links = link_extractor.extract_team_roster_links(html)
    assert isinstance(roster_links, list)
    assert all("Mannschaften" in l for l in roster_links)


def test_ranking_table_parsing():
    # pick a ranking table file
    html = read_sample("ranking_table_")
    division, teams = ranking_parser.parse_ranking_table(html, "ranking_table_DUMMY.html")
    assert isinstance(division, str)
    assert isinstance(teams, list)


def test_roster_player_and_match_parsing():
    html = read_sample("team_roster_")
    # Try to pull an id out of content fallback
    team_id = "test"
    matches = roster_parser.extract_matches(html, team_id=team_id)
    players = roster_parser.extract_players(html, team_id=team_id)
    assert isinstance(matches, list)
    assert isinstance(players, list)
