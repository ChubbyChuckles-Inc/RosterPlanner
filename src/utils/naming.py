"""Centralized filename and path naming utilities."""

from __future__ import annotations

import os
import re
from config import settings

_SANITIZE_PATTERN = re.compile(r"[^\w\s-]")
_WS_PATTERN = re.compile(r"[-\s]+")


def sanitize(value: str) -> str:
    value = _SANITIZE_PATTERN.sub("", value).strip()
    return _WS_PATTERN.sub("_", value)


def division_dir(base: str, division_name: str) -> str:
    return os.path.join(base, sanitize(division_name))


def team_roster_filename(division: str, team_name: str, team_id: str | None) -> str:
    div = sanitize(division)
    team = sanitize(team_name)
    suffix = team_id if team_id else "unknown"
    return f"team_roster_{div}_{team}_{suffix}.html"


def ranking_table_filename(division_name: str) -> str:
    return f"ranking_table_{sanitize(division_name)}.html"


def club_overview_filename(club_id: str) -> str:
    return f"club_overview_{club_id}.html"


def club_team_filename(club_id: str, team_name: str, team_id: str | None) -> str:
    team = sanitize(team_name)
    suffix = team_id if team_id else "unknown"
    return f"club_team_{club_id}_{team}_{suffix}.html"


def data_dir() -> str:
    return settings.DATA_DIR
