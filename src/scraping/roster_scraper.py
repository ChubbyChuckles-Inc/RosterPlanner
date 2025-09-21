"""Team roster scraping (extended)."""

from __future__ import annotations
from typing import List
import os
from core import http_client, filesystem
from utils import naming
from parsing import roster_parser
from domain.models import Match, Player


def fetch_roster(
    url: str, division: str, team_name: str, team_id: str | None, division_dir: str
) -> str:
    """Fetch a team roster page.

    division_dir should already be the filesystem path of the (sanitized) division
    directory. This avoids creating nested duplicate division folders (previous
    behavior nested division twice).
    """
    html = http_client.fetch(url)
    filename = naming.team_roster_filename(division, team_name, team_id)
    path = os.path.join(division_dir, filename)
    filesystem.write_text(path, html)
    return path


def parse_matches(html: str, team_id: str) -> List[Match]:
    return roster_parser.extract_matches(html, team_id=team_id)


def parse_players(html: str, team_id: str) -> List[Player]:
    return roster_parser.extract_players(html, team_id=team_id)
