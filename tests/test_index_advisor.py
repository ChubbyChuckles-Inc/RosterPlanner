from __future__ import annotations

import sqlite3
from pathlib import Path

from db.index_advisor import analyze_query_for_indexes, advise_indexes


def _setup(conn: sqlite3.Connection):
    conn.executescript(
        """
        CREATE TABLE player(id INTEGER PRIMARY KEY, name TEXT, club_id INTEGER, rating INTEGER);
        CREATE TABLE match(id INTEGER PRIMARY KEY, player_id INTEGER, opponent_id INTEGER, result TEXT);
        INSERT INTO player(name, club_id, rating) VALUES ('A',1,1200),('B',1,1100),('C',2,1300);
        INSERT INTO match(player_id, opponent_id, result) VALUES (1,2,'W'),(2,1,'L'),(3,1,'W');
        """
    )


def test_single_column_suggestion():
    conn = sqlite3.connect(":memory:")
    _setup(conn)
    # club_id filtered, no index exists
    suggestions = analyze_query_for_indexes(conn, "SELECT * FROM player WHERE club_id = 1")
    assert suggestions
    s = suggestions[0]
    assert s.table == "player"
    assert s.columns == ("club_id",)
    assert "CREATE INDEX" in s.create_sql


def test_composite_suggestion():
    conn = sqlite3.connect(":memory:")
    _setup(conn)
    suggestions = analyze_query_for_indexes(
        conn, "SELECT * FROM player WHERE club_id = 1 AND rating = 1200"
    )
    assert suggestions
    s = suggestions[0]
    assert s.columns == ("club_id", "rating")


def test_existing_index_skipped():
    conn = sqlite3.connect(":memory:")
    _setup(conn)
    conn.execute("CREATE INDEX idx_player_club_id ON player(club_id)")
    suggestions = analyze_query_for_indexes(conn, "SELECT * FROM player WHERE club_id = 1")
    assert suggestions == []


def test_advise_indexes_deduplicates():
    conn = sqlite3.connect(":memory:")
    _setup(conn)
    qs = [
        "SELECT * FROM player WHERE club_id = 1",
        "SELECT * FROM player WHERE club_id = 2",
    ]
    out = advise_indexes(conn, qs)
    assert len(out) == 1  # same pattern only one suggestion
