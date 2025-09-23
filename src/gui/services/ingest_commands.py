"""Command Palette integration for ingestion & data freshness (Milestone 5.9.22)

Registers two commands with the global command registry:

  ingest.force_reingest
      Re-runs the `IngestionCoordinator` over the currently registered
      data directory (service key: ``data_dir``) using the registered
      SQLite connection (service key: ``sqlite_conn``). Stores the
      resulting `IngestionSummary` under service key
      ``last_ingest_summary`` for retrieval by UI components and emits
      an event on the optional registered event bus (``event_bus``).

  data.show_freshness
      Computes a `DataFreshness` snapshot via `DataFreshnessService`
      and stores it under service key ``last_data_freshness``. This is
      intended for status bar updates or quick inspection via a future
      diagnostics panel.

Design Notes
------------
* Commands are lightweight, synchronous, and run on the GUI thread for now.
  A future enhancement can move ingestion to a worker thread if needed.
* Defensive: if required services are absent the command does nothing.
* Side-effect: prints a concise summary to stdout (useful in tests and
  during manual invocation without a GUI notification system yet).
"""

from __future__ import annotations

from typing import Optional
import sqlite3
from datetime import datetime

from .service_locator import services
from .command_registry import global_command_registry
from .ingestion_coordinator import IngestionCoordinator, IngestionSummary
from .data_freshness_service import DataFreshnessService, DataFreshness

__all__ = [
    "register_ingest_commands",
]


def _force_reingest() -> None:
    """Execute a synchronous re-ingest using currently registered services.

    Required services:
        * ``sqlite_conn``: sqlite3.Connection
        * ``data_dir``: path to directory containing HTML assets

    Optional services:
        * ``event_bus``: if present, receives a DATA_REFRESHED event (already
          emitted internally by coordinator if registered there). We emit a
          secondary lightweight event for UI listeners that prefer summary
          only.
    """

    data_dir: Optional[str] = services.try_get("data_dir")
    conn: Optional[sqlite3.Connection] = services.try_get("sqlite_conn")
    if not data_dir or not conn:
        print("[ingest.force_reingest] Missing data_dir or sqlite_conn; skipping")
        return
    coordinator = IngestionCoordinator(base_dir=data_dir, conn=conn, event_bus=services.try_get("event_bus"))  # type: ignore[arg-type]
    summary: IngestionSummary = coordinator.run(force=True)
    try:
        services.register("last_ingest_summary", summary, allow_override=True)
    except Exception:  # pragma: no cover - defensive
        pass
    print(
        f"[Ingest] divisions={summary.divisions_ingested} teams={summary.teams_ingested} files_processed={summary.processed_files} skipped={summary.skipped_files} errors={len(summary.errors)}"
    )
    # Emit a lightweight event if event bus present (non-fatal if missing)
    bus = services.try_get("event_bus")
    if bus is not None:  # pragma: no cover - event bus side-effect
        try:
            bus.publish("REINGEST_COMPLETED", {"summary": summary})
        except Exception:
            pass


def _show_freshness() -> None:
    """Capture current data freshness and store it for UI consumption."""

    svc = DataFreshnessService()
    snapshot: DataFreshness = svc.current()
    try:
        services.register("last_data_freshness", snapshot, allow_override=True)
    except Exception:  # pragma: no cover
        pass
    print(f"[Freshness] {snapshot.human_summary()}")


def register_ingest_commands() -> None:
    """Register ingestion-related commands if not already present."""

    global_command_registry.register(
        "ingest.force_reingest",
        "Force Re-ingest",
        _force_reingest,
        description="Re-run ingestion over current data set",
    )
    global_command_registry.register(
        "data.show_freshness",
        "Show Data Freshness",
        _show_freshness,
        description="Display last scrape & ingest timing",
    )


# Auto-register on import for convenience (idempotent due to registry guard)
register_ingest_commands()
