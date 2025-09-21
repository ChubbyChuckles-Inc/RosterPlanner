"""Club overview scraping (extended)."""

from __future__ import annotations
import os
from typing import Dict
from core import http_client, filesystem
from parsing import club_parser
from bs4 import BeautifulSoup  # type: ignore
from domain.models import Team
from utils import naming


def _extract_club_name(html: str) -> str | None:
    try:
        soup = BeautifulSoup(html, "html.parser")
        title = soup.find("title")
        if title and title.text:
            # Look for 'Vereinsinformation ' and take substring after it
            marker = "Vereinsinformation "
            if marker in title.text:
                return title.text.split(marker, 1)[1].strip()
    except Exception:
        return None
    return None


def fetch_and_parse_club(
    url: str, club_id: str, data_dir: str
) -> tuple[str | None, Dict[str, Team]]:
    html = http_client.fetch(url)
    club_name = _extract_club_name(html)
    # Persist using club name if available else fallback to id-based
    if club_name:
        filename = naming.club_overview_by_name_filename(club_name)
    else:
        filename = naming.club_overview_filename(club_id)
    clubs_dir = os.path.join(data_dir, "clubs")
    filesystem.write_text(os.path.join(clubs_dir, filename), html)
    teams = club_parser.extract_club_teams(html, club_id=club_id)
    # If club name available, patch team objects with normalized name via attribute if present
    if club_name:
        for t in teams.values():
            try:
                t.club_id = club_name  # repurpose for naming; original numeric id not strictly needed after this change
            except Exception:
                pass
    return club_name, teams
