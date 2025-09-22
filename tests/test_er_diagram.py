from __future__ import annotations
import sqlite3
import re
from db import apply_schema
from db.er import generate_er_mermaid


def test_er_diagram_contains_core_tables():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    apply_schema(conn)
    diagram = generate_er_mermaid(conn)
    for table in [
        "club",
        "division",
        "team",
        "player",
        "match",
        "availability",
        "planning_scenario",
        "scenario_player",
    ]:
        assert f"{table} {{" in diagram


def test_er_diagram_contains_relationships():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    apply_schema(conn)
    diagram = generate_er_mermaid(conn)
    # Compile relationship lines for robust matching
    lines = diagram.splitlines()
    rel_lines = [ln.strip() for ln in lines if re.search(r"}o--\|\|", ln)]

    def has_edge(pattern: str) -> bool:
        rx = re.compile(pattern)
        return any(rx.search(rl) for rl in rel_lines)

    # Patterns focus on table pair; allow any annotation details
    assert has_edge(r"^team }o--\|\| club")
    assert has_edge(r"^team }o--\|\| division")
    assert has_edge(r"^player }o--\|\| team")
    assert has_edge(r"^match }o--\|\| division")
    # Both home and away relationships should appear
    assert has_edge(r"^match }o--\|\| team.*home_team_id")
    assert has_edge(r"^match }o--\|\| team.*away_team_id")
    assert has_edge(r"^availability }o--\|\| player")
