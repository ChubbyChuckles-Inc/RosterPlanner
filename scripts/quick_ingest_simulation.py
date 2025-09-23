import sqlite3, pathlib, tempfile
from gui.services.ingestion_coordinator import IngestionCoordinator

html_ranking = """<html><head><title>TischtennisLive - Test Division - Tabelle</title></head><body></body></html>"""


def roster_tpl(team):
    return f"<html><body><table><tr><td>Spieler</td></tr><tr><td>1</td><td>.</td><td>.</td><td>{team} PlayerA</td><td>1500</td></tr></table></body></html>"


def run():
    with tempfile.TemporaryDirectory() as d:
        base = pathlib.Path(d)
        divdir = base / "Test_Division"
        divdir.mkdir()
        (divdir / "ranking_table_Test_Division.html").write_text(html_ranking, encoding="utf-8")
        for team in ["Alpha 1", "Alpha 2", "Alpha 3"]:
            fname = f"team_roster_Test_Division_{team.replace(' ','_')}_123.html"
            (divdir / fname).write_text(roster_tpl(team), encoding="utf-8")
        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE division(division_id INTEGER PRIMARY KEY, name TEXT, season INTEGER)"
        )
        conn.execute("CREATE TABLE club(club_id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute(
            "CREATE TABLE team(team_id INTEGER PRIMARY KEY, club_id INTEGER, division_id INTEGER, name TEXT)"
        )
        conn.execute(
            "CREATE TABLE player(player_id INTEGER PRIMARY KEY, team_id INTEGER, full_name TEXT, live_pz INTEGER)"
        )
        IngestionCoordinator(str(base), conn).run()
        teams = list(conn.execute("SELECT team_id,name FROM team"))
        players = list(conn.execute("SELECT team_id, full_name FROM player"))
        counts = {tid: sum(1 for t, _ in players if t == tid) for tid, _ in teams}
        print("Teams ingested:", teams)
        print("Player counts:", counts)


if __name__ == "__main__":
    run()
