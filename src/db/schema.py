"""SQLite Schema Definitions (Milestone 3.1)

Defines core tables for divisions, teams, matches, players, clubs, availability,
planning_scenarios. Provides helper to apply schema to a sqlite3 connection.

Design Principles:
 - Singular table names (roadmap 3.1.2 will formalize naming conventions)
 - Foreign keys enforced (caller must enable PRAGMA foreign_keys=ON)
 - Minimal indexes for primary lookup; performance indexes deferred to later tasks
 - Timestamps stored as ISO-8601 text (UTC)

Future Extensions:
 - Migration manager (Milestone 3.2) will use SCHEMA_VERSION constant.
"""

from __future__ import annotations
import sqlite3
from typing import Iterable

SCHEMA_VERSION = 1

# DDL statements (ordered for FK dependencies)
DDL: list[str] = [
    # Metadata table
    """
    CREATE TABLE IF NOT EXISTS schema_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """.strip(),
    # Club
    """
    CREATE TABLE IF NOT EXISTS club (
        club_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        short_name TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """.strip(),
    # Division
    """
    CREATE TABLE IF NOT EXISTS division (
        division_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        level TEXT,
        category TEXT, -- Erwachsene / Jugend
        season INTEGER NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """.strip(),
    # Team
    """
    CREATE TABLE IF NOT EXISTS team (
        team_id INTEGER PRIMARY KEY,
        club_id INTEGER NOT NULL REFERENCES club(club_id) ON DELETE CASCADE,
        division_id INTEGER NOT NULL REFERENCES division(division_id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        code TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(division_id, name)
    );
    """.strip(),
    # Player
    """
    CREATE TABLE IF NOT EXISTS player (
        player_id INTEGER PRIMARY KEY,
        team_id INTEGER REFERENCES team(team_id) ON DELETE SET NULL,
        full_name TEXT NOT NULL,
        live_pz INTEGER, -- rating snapshot
        position INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """.strip(),
    # Match
    """
    CREATE TABLE IF NOT EXISTS match (
        match_id INTEGER PRIMARY KEY,
        division_id INTEGER NOT NULL REFERENCES division(division_id) ON DELETE CASCADE,
        home_team_id INTEGER NOT NULL REFERENCES team(team_id) ON DELETE CASCADE,
        away_team_id INTEGER NOT NULL REFERENCES team(team_id) ON DELETE CASCADE,
        match_date TEXT NOT NULL,
        round INTEGER,
        home_score INTEGER,
        away_score INTEGER,
        status TEXT DEFAULT 'scheduled', -- scheduled/completed
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(division_id, home_team_id, away_team_id, match_date)
    );
    """.strip(),
    # Availability (unique per player/date)
    """
    CREATE TABLE IF NOT EXISTS availability (
        availability_id INTEGER PRIMARY KEY,
        player_id INTEGER NOT NULL REFERENCES player(player_id) ON DELETE CASCADE,
        date TEXT NOT NULL,
        status TEXT NOT NULL, -- available, doubtful, unavailable
        confidence INTEGER, -- optional 0-100
        note TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(player_id, date)
    );
    """.strip(),
    # Planning Scenario (simplified initial version)
    """
    CREATE TABLE IF NOT EXISTS planning_scenario (
        scenario_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        division_id INTEGER REFERENCES division(division_id) ON DELETE SET NULL,
        match_date TEXT,
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """.strip(),
    # Scenario Player Selection (lineup decisions)
    """
    CREATE TABLE IF NOT EXISTS scenario_player (
        scenario_id INTEGER NOT NULL REFERENCES planning_scenario(scenario_id) ON DELETE CASCADE,
        player_id INTEGER NOT NULL REFERENCES player(player_id) ON DELETE CASCADE,
        slot INTEGER, -- ordering or table spot
        role TEXT,    -- e.g., starter/reserve
        PRIMARY KEY (scenario_id, player_id)
    );
    """.strip(),
    # Indexes (basic)
    "CREATE INDEX IF NOT EXISTS idx_match_division_date ON match(division_id, match_date)",
    "CREATE INDEX IF NOT EXISTS idx_player_team ON player(team_id)",
    "CREATE INDEX IF NOT EXISTS idx_availability_player_date ON availability(player_id, date)",
]


def apply_schema(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    for stmt in DDL:
        cur.execute(stmt)
    # Set schema version
    cur.execute(
        "INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()


def get_existing_tables(conn: sqlite3.Connection) -> list[str]:
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return sorted(r[0] for r in cur.fetchall())
