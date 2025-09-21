"""Parsing of ranking table pages into division + team structures (BeautifulSoup)."""

from __future__ import annotations
import re
from typing import Dict, List, Tuple
from bs4 import BeautifulSoup
from domain.models import Team, Division


def extract_team_overview(html: str) -> Dict[str, Team]:
    soup = BeautifulSoup(html, "html.parser")
    teams: Dict[str, Team] = {}
    # Heuristic: rows with class ContentText / CONTENTTABLETEXT2ndLine and links containing L2P
    for tr in soup.find_all("tr"):
        cls = tr.get("class") or []
        if not any(c.lower() in {"contenttext", "contenttabletext2ndline"} for c in cls):
            continue
        tds = tr.find_all("td")
        if len(tds) < 4:
            continue
        # Attempt to locate anchor with L2P parameter
        link = tr.find("a", href=lambda h: h and "L2P=" in h)
        if not link:
            continue
        team_id_match = re.search(r"L2P=([^&]+)", link["href"])
        if not team_id_match:
            continue
        team_id = team_id_match.group(1)
        team_name = tds[1].get_text(strip=True)
        division_name = tds[2].get_text(strip=True)
        if team_id and team_name and division_name:
            teams[team_id] = Team(id=team_id, name=team_name, division_name=division_name)
    return teams


def build_divisions(teams: Dict[str, Team]) -> Dict[str, Division]:
    divisions: Dict[str, Division] = {}
    for t in teams.values():
        if not t.division_name:
            continue
        divisions.setdefault(t.division_name, Division(name=t.division_name)).teams.append(t)
    return divisions


def parse_ranking_table(html: str, filename: str) -> Tuple[str, List[dict]]:
    soup = BeautifulSoup(html, "html.parser")
    division_name = filename.replace("ranking_table_", "").replace(".html", "")
    division_name = re.sub(r"_+", " ", division_name).strip()
    teams: List[dict] = []
    # Find Mannschaften navigation entry, then sibling UL
    nav_links = [a for a in soup.find_all("a") if a.get_text(strip=True).lower() == "mannschaften"]
    for a in nav_links:
        parent_li = a.find_parent("li")
        if not parent_li:
            continue
        ul = parent_li.find("ul")
        if not ul:
            continue
        for li in ul.find_all("li"):
            roster_a = li.find("a", href=True)
            span = li.find("span")
            if roster_a and span:
                href = roster_a["href"]
                tname = span.get_text(strip=True)
                if tname and href:
                    teams.append({"team_name": tname, "roster_link": href})
    return division_name, teams
