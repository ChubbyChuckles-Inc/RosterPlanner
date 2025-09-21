"""Parsing of club overview pages to list teams (BeautifulSoup refactor)."""

from __future__ import annotations
import re
from typing import Dict
from bs4 import BeautifulSoup  # type: ignore
from domain.models import Team
from utils import html_utils

ROSTER_LINK_TEMPLATE = "?L1=Ergebnisse&L2=TTStaffeln&L2P={id}&L3=Mannschaften&L3P={id}"


def extract_club_teams(html: str, *, club_id: str) -> Dict[str, Team]:
    """Extract teams for a club.

    Heuristic: rows with classes ContentText or CONTENTTABLETEXT2ndLine contain columns:
        (ignored index) | team name | division | link with L2P=team_id
    We parse anchor href to obtain team id (L2P param). Fallback: attempt regex extraction if href missing.
    """
    soup = BeautifulSoup(html, "html.parser")
    teams: Dict[str, Team] = {}
    for tr in soup.find_all(
        "tr",
        class_=lambda c: c and any(cls in c for cls in ["ContentText", "CONTENTTABLETEXT2ndLine"]),
    ):
        tds = tr.find_all("td")
        if len(tds) < 4:
            continue
        # Columns: 0 index, 1 name, 2 division, 3 link container
        name = html_utils.clean_cell(tds[1].get_text(strip=True))
        division = html_utils.clean_cell(tds[2].get_text(strip=True))
        link_td = tds[3]
        a = link_td.find("a", href=lambda h: h and "L2P=" in h)
        if not a:
            continue
        href = a.get("href", "")
        m = re.search(r"L2P=([^&]+)", href)
        if not m:
            continue
        team_id = m.group(1)
        if name and division and team_id:
            teams[team_id] = Team(id=team_id, name=name, division_name=division, club_id=club_id)
    return teams


def build_roster_link(team_id: str) -> str:
    return ROSTER_LINK_TEMPLATE.format(id=team_id)
