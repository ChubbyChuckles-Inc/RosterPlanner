"""Initial link extraction from landing page HTML (BeautifulSoup version)."""

from __future__ import annotations
from bs4 import BeautifulSoup
from utils.html_utils import dedupe

ROOT_URL = "https://leipzig.tischtennislive.de/"


def extract_team_roster_links(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "L3=Mannschaften" in href:
            links.append(href)
    return dedupe(links)


def derive_ranking_table_links(team_roster_links: list[str]) -> list[str]:
    ranking_links: list[str] = []
    for roster_link in team_roster_links:
        # Extract prefix up to L2P param if present
        # Example: ?L1=Ergebnisse&L2=TTStaffeln&L2P=12345&L3=Mannschaften&L3P=12345
        try:
            base_part = roster_link.split("&L3=")[0]
            if "L2=TTStaffeln" in base_part:
                ranking_links.append(f"{ROOT_URL}{base_part}&L3=Tabelle")
        except Exception:
            continue
    return dedupe(ranking_links)
