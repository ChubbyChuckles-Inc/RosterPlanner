"""Edge case tests for statistics services (Milestone 6.8).

Covers:
 - Empty team (no players, no matches)
 - Partial season (some matches without scores ignored)
 - Missing LivePZ values
 - Predictor neutral distribution when insufficient data
 - Division strength index with single team
"""

from __future__ import annotations

import sqlite3
import pytest

from gui.services.service_locator import services
from gui.services.stats_service import StatsService
from src.services.match_outcome_predictor_service import MatchOutcomePredictorService
from gui.services.division_strength_index_service import DivisionStrengthIndexService


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    cur = c.cursor()
    cur.execute(
        "CREATE TABLE team(team_id TEXT PRIMARY KEY, name TEXT, division_id TEXT, club_id TEXT)"
    )
    cur.execute(
        "CREATE TABLE player(player_id TEXT PRIMARY KEY, full_name TEXT, team_id TEXT, live_pz INTEGER)"
    )
    cur.execute(
        "CREATE TABLE match(match_id INTEGER PRIMARY KEY AUTOINCREMENT, division_id TEXT, home_team_id TEXT, away_team_id TEXT, match_date TEXT, round INTEGER, home_score INTEGER, away_score INTEGER, status TEXT)"
    )
    c.commit()
    services.register("sqlite_conn", c, allow_override=True)
    try:
        yield c
    finally:
        services.unregister("sqlite_conn")
        c.close()


def test_empty_team_stats(conn):
    svc = StatsService(conn)
    assert svc.team_win_percentage("NO_TEAM") is None
    assert svc.average_top_live_pz("NO_TEAM") is None
    assert svc.player_participation_rate("NO_TEAM") == {}


def test_partial_season_ignores_incomplete(conn):
    cur = conn.cursor()
    cur.execute("INSERT INTO team(team_id,name,division_id) VALUES(?,?,?)", ("T1", "Alpha", "D1"))
    # Completed match and upcoming (NULL scores)
    cur.execute(
        "INSERT INTO match(division_id, home_team_id, away_team_id, match_date, home_score, away_score, status) VALUES(?,?,?,?,?,?,?)",
        ("D1", "T1", "T1", "2025-01-01", 9, 0, "completed"),
    )
    cur.execute(
        "INSERT INTO match(division_id, home_team_id, away_team_id, match_date, status) VALUES(?,?,?,?,?)",
        ("D1", "T1", "T1", "2025-01-08", "scheduled"),
    )
    conn.commit()
    svc = StatsService(conn)
    pct = svc.team_win_percentage("T1")
    assert pct == 1.0  # second match ignored


def test_missing_livepz_values(conn):
    cur = conn.cursor()
    cur.execute("INSERT INTO team(team_id,name,division_id) VALUES(?,?,?)", ("T1", "Alpha", "D1"))
    # Players with some missing LivePZ
    cur.execute(
        "INSERT INTO player(player_id, full_name, team_id, live_pz) VALUES(?,?,?,?)",
        ("P1", "A1", "T1", 1500),
    )
    cur.execute(
        "INSERT INTO player(player_id, full_name, team_id, live_pz) VALUES(?,?,?,?)",
        ("P2", "A2", "T1", None),
    )
    conn.commit()
    svc = StatsService(conn)
    avg = svc.average_top_live_pz("T1", top_n=4)
    assert avg == 1500  # only one valid LivePZ


def test_predictor_neutral_when_insufficient():
    predictor = MatchOutcomePredictorService(top_n=3)
    pred = predictor.predict([None, None], [1600, 1500])
    assert pred.outcome == "draw"
    assert abs(pred.p_win + pred.p_draw + pred.p_lose - 1.0) < 1e-9


def test_division_strength_single_team(conn):
    cur = conn.cursor()
    cur.execute("INSERT INTO team(team_id,name,division_id) VALUES(?,?,?)", ("Tsolo", "Solo", "D1"))
    conn.commit()
    svc = DivisionStrengthIndexService()
    result = svc.compute_division("D1")
    assert result is not None
    assert len(result.team_ratings) == 1
    # Average equals the sole team rating
    assert abs(result.average_rating - list(result.team_ratings.values())[0]) < 1e-9
