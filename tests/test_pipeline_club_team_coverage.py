import os
import re
from services import pipeline
from core import filesystem


PRIMARY_CLUB_ID = 9999


def _fake_http_fetch(url: str):  # simplistic stub
    # Provide different HTML depending on pattern
    # IMPORTANT: check for specific club overview first; otherwise the generic landing condition below would shadow it
    if "Verein" in url and f"L2P={PRIMARY_CLUB_ID}" in url and "Page=Spielbetrieb" in url:
        # Club overview with multiple teams (simulate ~5 teams for speed)
        rows = []
        for i in range(5):
            team_id = 5000 + i
            rows.append(
                f"<tr class='ContentText'><td>{i+1}</td><td>Füchse Team {i+1}</td><td>1. Stadtliga Gruppe {i+1}</td>"
                f"<td><a href='?L1=Ergebnisse&L2=TTStaffeln&L2P={team_id}&L3=Mannschaften&L3P={team_id}'>Roster</a></td></tr>"
            )
        return (
            "<html><title>Vereinsinformation Leutzscher Füchse</title><table>"
            + "".join(rows)
            + "</table></html>"
        )
    if "Page=Spielbetrieb" in url:
        # Landing page minimal with no extra roster links; return benign HTML (used for initial landing fetch)
        return "<html><body><table></table></body></html>"
    if "L1=Ergebnisse" in url and "Mannschaften" in url:
        # Roster page placeholder with club link reference
        return '<html><a href="?L1=Public&L2=Verein&L2P=9999&Page=Spielbetrieb"></a></html>'
    return "<html></html>"


class _HttpClientMonkey:
    def __init__(self, module):
        self.module = module
        self.orig = module.http_client.fetch

    def __enter__(self):
        self.module.http_client.fetch = _fake_http_fetch  # type: ignore

    def __exit__(self, exc_type, exc, tb):
        self.module.http_client.fetch = self.orig  # type: ignore


def test_pipeline_fetches_all_club_overview_teams(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    os.makedirs(data_dir, exist_ok=True)
    # Monkeypatch ranking_scraper & club_scraper http fetch
    from scraping import ranking_scraper, club_scraper

    # Monkeypatch club_scraper.fetch_and_parse_club to reuse _fake_http_fetch without double writes
    orig_fetch_and_parse = club_scraper.fetch_and_parse_club

    def _fake_fetch_and_parse(url, club_id, data_dir):  # mimic original signature
        html = _fake_http_fetch(url)
        # Parse teams directly using real parser to stay close to prod logic
        from parsing import club_parser

        teams = club_parser.extract_club_teams(html, club_id=str(club_id))
        return "Leutzscher Füchse", teams

    club_scraper.fetch_and_parse_club = _fake_fetch_and_parse  # type: ignore
    try:
        with _HttpClientMonkey(ranking_scraper), _HttpClientMonkey(club_scraper):
            pipeline.run_full(PRIMARY_CLUB_ID, season=2025, data_dir=str(data_dir))
    finally:
        club_scraper.fetch_and_parse_club = orig_fetch_and_parse  # type: ignore
    # Expect 5 club team pages generated
    club_team_dir = data_dir / "club_teams"
    assert club_team_dir.exists()
    club_team_files = [f for f in os.listdir(club_team_dir) if f.endswith(".html")]
    assert len(club_team_files) == 5
    # Expect corresponding division or fallback unknown division roster files present
    roster_files = []
    for root, dirs, files in os.walk(data_dir):
        for f in files:
            if f.startswith("team_roster_") and f.endswith(".html"):
                roster_files.append(f)
    # At least 5 new roster files referencing the teams
    # They may have either sanitized division names or unknown_division
    matched = 0
    for i in range(5):
        pattern = re.compile(rf"team_roster_.*_Füchse_Team_{i+1}_5\d\d\d.html")
        if any(pattern.match(rf) for rf in roster_files):
            matched += 1
    assert matched == 5, f"Expected 5 roster files for club overview teams, found {matched}"
