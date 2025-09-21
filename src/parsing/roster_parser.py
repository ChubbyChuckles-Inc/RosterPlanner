"""Parsing of team roster pages for matches, players, club links (BeautifulSoup refactor)."""

from __future__ import annotations
import re
from typing import List
from bs4 import BeautifulSoup  # type: ignore
from domain.models import Match, Player
from utils import html_utils


def _cell_text(cell) -> str:
    return html_utils.clean_cell(cell.get_text(" ", strip=True)) if cell else ""


def extract_matches(html: str, *, team_id: str) -> List[Match]:
    """Extract match rows from a roster page.

    Heuristics: rows with an id attribute starting with 'Spiel' contain match data.
    We rely on positional columns similar to legacy mapping; if the structure shifts, we skip incomplete rows.
    """
    soup = BeautifulSoup(html, "html.parser")
    matches: List[Match] = []
    # Find all tr elements whose id matches Spiel\d+
    for tr in soup.find_all("tr", id=re.compile(r"Spiel\d+", re.IGNORECASE)):
        tds = tr.find_all("td")
        if len(tds) < 10:
            continue
        clean = [_cell_text(td) for td in tds]
        match_number = clean[1] if len(clean) > 1 else None
        weekday = clean[3] if len(clean) > 3 else None
        date = clean[4] if len(clean) > 4 else None
        time = clean[6] if len(clean) > 6 else None
        home_team = clean[7] if len(clean) > 7 else ""
        guest_team = clean[8] if len(clean) > 8 else ""
        score_field = clean[9] if len(clean) > 9 else ""
        status = "upcoming"
        home_score = guest_score = None
        m = re.search(r"(\d+):(\d+)", score_field)
        if m:
            status = "completed"
            home_score = int(m.group(1))
            guest_score = int(m.group(2))
        matches.append(
            Match(
                team_id=team_id,
                match_number=match_number,
                date=date,
                time=time,
                weekday=weekday,
                home_team=home_team,
                guest_team=guest_team,
                home_score=home_score,
                guest_score=guest_score,
                status=status,
            )
        )
    return matches


def extract_players(html: str, *, team_id: str) -> List[Player]:
    """Extract player rows with LivePZ values.

    Primary approach: iterate over rows containing an anchor to a Spieler page and a tooltip cell with title containing 'LivePZ-Wert'.
    Fallback: separate collection of anchors and tooltip cells if row pairing fails.
    """
    soup = BeautifulSoup(html, "html.parser")
    players: List[Player] = []

    # Row-based extraction
    for a in soup.find_all("a", href=lambda h: h and "Spieler" in h):
        tr = a.find_parent("tr")
        if not tr:
            continue
        tooltip_td = tr.find(
            "td",
            class_=lambda c: c and "tooltip" in c.split(),
            title=lambda t: t and "LivePZ-Wert" in t,
        )
        name = html_utils.clean_cell(a.get_text(strip=True))
        number = None
        if tooltip_td:
            num_candidate = html_utils.extract_last_number(_cell_text(tooltip_td))
            number = int(num_candidate) if num_candidate else None
        players.append(Player(team_id=team_id, name=name, live_pz=number))

    # If nothing found, fallback to legacy anchor + tooltip pairing
    if not players:
        name_anchors = [
            html_utils.clean_cell(a.get_text(strip=True))
            for a in soup.find_all("a", href=lambda h: h and "Spieler" in h)
            if html_utils.clean_cell(a.get_text(strip=True))
        ]
        tooltip_cells = [
            td
            for td in soup.find_all(
                "td",
                class_=lambda c: c and "tooltip" in c.split(),
                title=lambda t: t and "LivePZ-Wert" in t,
            )
        ]
        pz_values: List[int | None] = []
        for td in tooltip_cells:
            num_candidate = html_utils.extract_last_number(_cell_text(td))
            pz_values.append(int(num_candidate) if num_candidate else None)
        for idx, name in enumerate(name_anchors):
            pz = pz_values[idx] if idx < len(pz_values) else None
            players.append(Player(team_id=team_id, name=name, live_pz=pz))

    # Deduplicate by name preserving first occurrence
    seen: set[str] = set()
    deduped: List[Player] = []
    for p in players:
        if p.name not in seen:
            seen.add(p.name)
            deduped.append(p)
    return deduped


def extract_club_link(html: str) -> str | None:
    """Return the first club link (anchor text 'Verein')."""
    soup = BeautifulSoup(html, "html.parser")
    a = soup.find(
        "a",
        href=lambda h: h and "L2=Verein" in h,
        string=lambda s: s and s.strip().lower() == "verein",
    )
    return a["href"] if a and a.has_attr("href") else None
