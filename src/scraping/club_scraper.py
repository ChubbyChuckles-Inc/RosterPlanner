"""Club overview scraping (extended)."""

from __future__ import annotations
import os
from typing import Dict
from core import http_client, filesystem
from parsing import club_parser
from domain.models import Team
from utils import naming


def fetch_and_parse_club(url: str, club_id: str, data_dir: str) -> Dict[str, Team]:
    html = http_client.fetch(url)
    filename = naming.club_overview_filename(club_id)
    clubs_dir = os.path.join(data_dir, "clubs")
    filesystem.write_text(os.path.join(clubs_dir, filename), html)
    return club_parser.extract_club_teams(html, club_id=club_id)
