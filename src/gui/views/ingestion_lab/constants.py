"""Constants used across the ingestion lab panel implementation."""

from __future__ import annotations

from typing import Callable, Tuple

__all__ = ["HTML_EXTENSIONS", "PHASE_PATTERNS", "OTHER_PHASE_ID"]

HTML_EXTENSIONS = {".html", ".htm"}

# Phase grouping heuristics (Milestone 7.10.2). Each entry is (phase_id, display_label, predicate)
# The predicate receives (relative_path, filename_lower) and returns True if the file belongs.
PhasePredicate = Callable[[str, str], bool]
PhasePattern = Tuple[str, str, PhasePredicate]

PHASE_PATTERNS: list[PhasePattern] = [
    ("ranking_tables", "Ranking Tables", lambda rel, fn: fn.startswith("ranking_table_")),
    ("team_rosters", "Team Rosters", lambda rel, fn: fn.startswith("team_roster_")),
    ("club_overviews", "Club Overviews", lambda rel, fn: "club" in fn and "overview" in fn),
    ("player_histories", "Player Histories", lambda rel, fn: "history" in fn or "tracking" in fn),
]
OTHER_PHASE_ID = "other"
