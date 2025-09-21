"""Global configuration and constants for scraping pipeline."""

from __future__ import annotations

import os
from typing import Final

ROOT_URL: Final = "https://leipzig.tischtennislive.de/"
DEFAULT_USER_AGENT: Final = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"
)
DEFAULT_TIMEOUT: Final = 15  # seconds
DEFAULT_RETRIES: Final = 3
DEFAULT_BACKOFF_FACTOR: Final = 0.6
DATA_DIR: Final = os.environ.get("ROSTERPLANNER_DATA_DIR", "data")

# Seasons can be parameterized later; keep here for centralization
DEFAULT_SEASON: Final = 2025
