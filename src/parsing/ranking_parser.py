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


def parse_ranking_table(html: str, source_hint: str | None = None) -> Tuple[str, List[dict]]:
    """Parse a ranking table page and return (division_name, teams).

    division_name extraction strategy (in order):
      1. Page title (<title>) pattern: ' - <Division Name> - Tabelle'
      2. Headline table (td within table.PageHeadline) textual content (excluding season year pattern '20xx/yy').
      3. Fallback to source_hint sanitized (legacy behaviour using filename) with underscores replaced by spaces.
    """
    soup = BeautifulSoup(html, "html.parser")
    division_name: str | None = None

    # Strategy 1: title tag
    title = soup.title.get_text(strip=True) if soup.title else ""
    # Example: 'TischtennisLive - Bezirksverband Leipzig - 1. Bezirksliga Erwachsene - Tabelle'
    if title:
        parts = [p.strip() for p in title.split(" - ") if p.strip()]
        # Division likely the last non 'Tabelle' segment before 'Tabelle'
        if parts and parts[-1].lower() == "tabelle" and len(parts) >= 2:
            division_name = parts[-2]
    # Strategy 2: headline table cell (PageHeadline)
    if not division_name:
        headline_td = None
        for td in soup.find_all("td"):
            parent = td.find_parent("table")
            classes = parent.get("class") if parent else []
            if parent and classes and any("PageHeadline" in c for c in classes):
                text = td.get_text(" ", strip=True)
                if text and not re.search(r"20\d{2}/\d{2}", text):
                    headline_td = text
                    break
        if headline_td:
            division_name = headline_td

    # Augment: if division_name is overly short / generic like 'Gruppe 2', look for richer context.
    if division_name and re.fullmatch(r"Gruppe\s+\d+", division_name):
        # Search title again for preceding tokens containing 'Jugend' or 'Vorrunde'
        if title:
            parts = [p.strip() for p in title.split(" - ") if p.strip()]
            # Find any segment containing 'Gruppe' and rebuild from prior 2 parts if they have Jugend/Vorrunde
            for i, seg in enumerate(parts):
                if re.search(r"Gruppe\s+\d+", seg):
                    prefix_parts = []
                    for back in range(1, 4):
                        if i - back >= 0:
                            cand = parts[i - back]
                            if re.search(r"Jugend", cand, re.IGNORECASE) or re.search(
                                r"Vorrunde", cand, re.IGNORECASE
                            ):
                                prefix_parts.insert(0, cand)
                    if prefix_parts:
                        division_name = " ".join(prefix_parts + [seg])
                    break
    # Strategy 3: fallback to source hint (filename previously)
    if not division_name:
        if source_hint:
            division_name = source_hint.replace("ranking_table_", "").replace(".html", "")
            division_name = re.sub(r"_+", " ", division_name).strip()
        else:
            division_name = "Unknown_Division"

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
