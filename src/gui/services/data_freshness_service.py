"""DataFreshnessService (Milestone 5.9.11)

Tracks and reports *when* the last scrape and the last ingest occurred so the
GUI can inform users about data staleness.

Definitions
-----------
last scrape:
    Timestamp stored in the tracking state JSON file (``match_tracking.json``)
    written by the scraping pipeline (``tracking_store.save_state``) after a
    successful scrape run.
last ingest:
    The most recent timestamp an ingestion pass wrote rows into the database.
    Sourced preferentially from ``provenance_summary.ingested_at`` (one row per
    ingest summary). Falls back to the max ``provenance.last_ingested_at`` when
    the summary table is absent (e.g. legacy / partial schema during tests).

Provided API
------------
``DataFreshnessService.current()`` returns a ``DataFreshness`` dataclass with:
    * ``last_scrape`` (datetime|None)
    * ``last_ingest`` (datetime|None)
    * ``age_since_scrape_seconds`` (int|None)
    * ``age_since_ingest_seconds`` (int|None)

Utility helpers for simple humanized relative strings are also included so the
MainWindow can append a concise status (e.g. ``Scrape: 2h ago | Ingest: 5m ago``).

Design Notes
------------
- Pure read-only service; safe to instantiate per call (no internal caching).
- Defensive: all DB / file errors are swallowed returning ``None`` fields.
- Timezone: timestamps are treated as *UTC* (pipeline uses ``datetime.utcnow`` /
  SQLite ``CURRENT_TIMESTAMP``). We compare against ``datetime.utcnow`` for age.
- Parsing tolerance: supports ISO-8601 with or without fractional seconds and
  SQLite ``YYYY-MM-DD HH:MM:SS`` format.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
import json
import sqlite3

from .service_locator import services

TRACKING_FILENAME = "match_tracking.json"

__all__ = [
    "DataFreshness",
    "DataFreshnessService",
]


@dataclass(frozen=True)
class DataFreshness:
    """Snapshot of current data freshness state."""

    last_scrape: Optional[datetime]
    last_ingest: Optional[datetime]
    age_since_scrape_seconds: Optional[int]
    age_since_ingest_seconds: Optional[int]

    def human_summary(self) -> str:
        """Return a concise human-readable summary string.

        Examples:
            "Scrape: 2h ago | Ingest: 5m ago"
            "Scrape: never | Ingest: never"
        """

        def _fmt(dt: Optional[datetime], age: Optional[int]) -> str:
            if dt is None or age is None:
                return "never"
            return humanize_age(age)

        return f"Scrape: {_fmt(self.last_scrape, self.age_since_scrape_seconds)} | Ingest: {_fmt(self.last_ingest, self.age_since_ingest_seconds)}"


def _parse_timestamp(raw: str) -> Optional[datetime]:
    """Attempt to parse a timestamp from several known formats.

    Accepts:
        * ISO8601 (``datetime.fromisoformat``) with or without 'Z'
        * SQLite default ``YYYY-MM-DD HH:MM:SS``
    Returns ``None`` if parsing fails.
    """

    raw = raw.strip()
    if not raw:
        return None
    # Remove trailing Z for fromisoformat compatibility
    if raw.endswith("Z"):
        raw = raw[:-1]
    try:
        return datetime.fromisoformat(raw)
    except Exception:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(raw, fmt)
        except Exception:
            continue
    return None


def humanize_age(seconds: int) -> str:
    """Return a compact human description for an age in seconds.

    Priority units: days (d), hours (h), minutes (m), seconds (s).
    We surface the *largest* non-zero unit (except we show seconds if < 60).
    """

    if seconds < 0:
        return "0s"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    if d > 0:
        return f"{d}d ago"
    if h > 0:
        return f"{h}h ago"
    if m > 0:
        return f"{m}m ago"
    return f"{s}s ago"


class DataFreshnessService:
    """Service fetching scrape + ingest recency information.

    Parameters
    ----------
    base_dir: str | None
        Directory containing tracking JSON (defaults to current data dir
        discovered via services if not provided).
    conn: sqlite3.Connection | None
        Optional explicit DB connection; if omitted, resolves via service
        locator key ``sqlite_conn``.
    """

    def __init__(self, base_dir: str | None = None, conn: sqlite3.Connection | None = None):
        self.base_dir = base_dir or services.try_get("data_dir") or "."
        self.conn = conn or services.try_get("sqlite_conn")

    # Public API -------------------------------------------------
    def current(self) -> DataFreshness:
        last_scrape = self._load_last_scrape()
        last_ingest = self._load_last_ingest()
        now = datetime.utcnow()
        age_scrape = int((now - last_scrape).total_seconds()) if last_scrape else None
        age_ingest = int((now - last_ingest).total_seconds()) if last_ingest else None
        return DataFreshness(
            last_scrape=last_scrape,
            last_ingest=last_ingest,
            age_since_scrape_seconds=age_scrape,
            age_since_ingest_seconds=age_ingest,
        )

    # Internal helpers ------------------------------------------
    def _load_last_scrape(self) -> Optional[datetime]:
        try:
            p = Path(self.base_dir) / TRACKING_FILENAME
            if not p.exists():
                return None
            raw = json.loads(p.read_text(encoding="utf-8"))
            ts_raw = raw.get("last_scrape")
            if not ts_raw:
                return None
            return _parse_timestamp(ts_raw)
        except Exception:
            return None

    def _load_last_ingest(self) -> Optional[datetime]:
        if not self.conn:
            return None
        cur = None
        # Prefer provenance_summary
        try:
            cur = self.conn.execute(
                "SELECT ingested_at FROM provenance_summary ORDER BY ingested_at DESC LIMIT 1"
            )
            row = cur.fetchone()
            if row and row[0]:
                parsed = _parse_timestamp(str(row[0]))
                if parsed:
                    return parsed
        except Exception:
            pass
        # Fallback: provenance (file-level) last_ingested_at
        try:
            cur = self.conn.execute(
                "SELECT last_ingested_at FROM provenance ORDER BY last_ingested_at DESC LIMIT 1"
            )
            row = cur.fetchone()
            if row and row[0]:
                parsed = _parse_timestamp(str(row[0]))
                if parsed:
                    return parsed
        except Exception:
            pass
        return None
