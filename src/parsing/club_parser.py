"""Parsing of club overview pages to list teams (BeautifulSoup refactor)."""

from __future__ import annotations
import re
from typing import Dict
from bs4 import BeautifulSoup  # type: ignore
from domain.models import Team
from utils import html_utils

# Roster link template: We explicitly request the 'Vorrunde' page variant because the default
# landing (without &Page=) can sometimes omit the immediate player table (depending on
# server-side state or caching). By forcing &Page=Vorrunde we consistently receive the
# roster section including player anchor rows and LivePZ tooltip cells used by the parser.
ROSTER_LINK_TEMPLATE = (
    "?L1=Ergebnisse&L2=TTStaffeln&L2P={division_id}&L3=Mannschaften&L3P={team_id}&Page=Vorrunde"
)


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
        # Distinguish division_id vs team_id if both parameters present (L2P & L3P). Legacy pages may only contain L2P.
        m_div = re.search(r"L2P=([^&]+)", href)
        m_team = re.search(r"L3P=([^&]+)", href)
        division_id = m_div.group(1) if m_div else None
        team_id = m_team.group(1) if m_team else (division_id or None)
        if name and division and team_id:
            teams[team_id] = Team(
                id=team_id,
                name=name,
                division_name=division,
                club_id=club_id,
                division_id=division_id,
            )
    return teams


def build_roster_link(team_id: str, division_id: str | None = None) -> str:
    # If division_id missing, fall back to team_id (legacy behaviour) to avoid breaking callers, but mark for repair.
    div_id = division_id or team_id
    link = ROSTER_LINK_TEMPLATE.format(division_id=div_id, team_id=team_id)
    if "Page=" not in link:
        sep = "&" if "?" in link else "?"
        link = f"{link}{sep}Page=Vorrunde"
    return link
