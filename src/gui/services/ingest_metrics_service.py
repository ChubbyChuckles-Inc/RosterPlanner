"""IngestMetricsService

Tracks recent ingestion runs (counts + duration) for surfacing lightweight
operational telemetry in the status bar (replacing synthetic placeholder
trend metrics). Designed to be ephemeral in-memory state; persistence is not
required for the immediate UX goal.

API (stable subset):
    ingest_metrics = IngestMetricsService(max_runs=20)
    ingest_metrics.append_from_summary(summary, duration_ms)
    ingest_metrics.recent_runs() -> list[IngestRunStat] (oldest->newest)
    ingest_metrics.last_run() -> IngestRunStat | None

The service is intentionally decoupled from IngestionCoordinator except for
the *append* call performed at the end of a run (best effort). It is registered
in the global service locator under key ``ingest_metrics`` when first needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections import deque
from typing import Deque, List, Optional
import time

__all__ = ["IngestRunStat", "IngestMetricsService"]


@dataclass(frozen=True)
class IngestRunStat:
    ts: float  # epoch seconds (UTC)
    duration_ms: int
    divisions_ingested: int
    teams_ingested: int
    players_ingested: int
    processed_files: int
    skipped_files: int
    error_count: int
    warn_count: int


class IngestMetricsService:
    def __init__(self, max_runs: int = 20):
        self._runs: Deque[IngestRunStat] = deque(maxlen=max_runs)

    # Recording --------------------------------------------------
    def append_from_summary(self, summary, duration_ms: float):  # pragma: no cover - thin
        """Append a run stat derived from an ``IngestionSummary``.

        ``summary``: IngestionSummary (duck-typed: attribute access only)
        ``duration_ms``: float | int duration in milliseconds
        """
        errors = getattr(summary, "errors", []) or []
        error_count = sum(1 for e in errors if getattr(e, "severity", "error") == "error")
        warn_count = sum(1 for e in errors if getattr(e, "severity", "error") == "warn")
        stat = IngestRunStat(
            ts=time.time(),
            duration_ms=int(duration_ms),
            divisions_ingested=getattr(summary, "divisions_ingested", 0) or 0,
            teams_ingested=getattr(summary, "teams_ingested", 0) or 0,
            players_ingested=getattr(summary, "players_ingested", 0) or 0,
            processed_files=getattr(summary, "processed_files", 0) or 0,
            skipped_files=getattr(summary, "skipped_files", 0) or 0,
            error_count=error_count,
            warn_count=warn_count,
        )
        self._runs.append(stat)

    # Accessors --------------------------------------------------
    def recent_runs(self) -> List[IngestRunStat]:
        return list(self._runs)

    def last_run(self) -> Optional[IngestRunStat]:
        return self._runs[-1] if self._runs else None
