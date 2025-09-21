"""High-level ranking table scraping logic (extended)."""

from __future__ import annotations
from typing import Dict, List
import os
from core import http_client, filesystem
from parsing import ranking_parser
from domain.models import Team, Division
from utils import naming


def fetch_and_parse_overview(url: str) -> Dict[str, Team]:
    html = http_client.fetch(url)
    return ranking_parser.extract_team_overview(html)


def fetch_ranking_table(url: str, division_name_hint: str, data_dir: str) -> str:
    """Fetch and persist a ranking table using a provided division name hint.

    Note: The pipeline now prefers to fetch HTML and parse the real division name
    before persisting. This helper remains for backwards compatibility or ad-hoc
    usage (e.g. tests) and still writes using the hint.
    """
    html = http_client.fetch(url)
    filename = naming.ranking_table_filename(division_name_hint)
    path = os.path.join(data_dir, filename)
    filesystem.write_text(path, html)
    return path
