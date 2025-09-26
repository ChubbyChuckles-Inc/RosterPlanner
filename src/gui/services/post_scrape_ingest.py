"""Post-scrape automatic ingestion hook (Milestone 5.9.5).

Listens for `ScrapeRunner.scrape_finished` (GUI signal) and triggers the
`IngestionCoordinator` to ingest newly scraped HTML assets. This closes the
loop: scrape -> ingest -> DATA_REFRESHED event for views.

Design choices:
- Keeps responsibilities separated: ScrapeRunner focuses on scraping,
  coordinator focuses on ingestion, this hook orchestrates the sequence.
- Uses service locator to retrieve shared `event_bus` and a registered
  SQLite connection (optional). If connection not present, ingestion is
  skipped gracefully (logged via event bus ERROR_OCCURRED placeholder).
"""

from __future__ import annotations

from typing import Optional, Any
import sqlite3

from .service_locator import services
from .event_bus import GUIEvent, EventBus
from .ingestion_coordinator import IngestionCoordinator

try:  # optional import; GUI may not always have lab components loaded
    from gui.views.ingestion_lab_panel import IngestionLabPanel  # type: ignore
except Exception:  # pragma: no cover
    IngestionLabPanel = None  # type: ignore

__all__ = ["PostScrapeIngestionHook"]


class PostScrapeIngestionHook:
    def __init__(self, scrape_runner, data_dir_provider):
        """Attach to a `ScrapeRunner` instance.

        Parameters
        ----------
        scrape_runner: ScrapeRunner
            Instance whose `scrape_finished` signal we observe.
        data_dir_provider: callable returning current data directory string.
            Indirection allows dynamic path changes (user switching project directory).
        """
        self._runner = scrape_runner
        self._data_dir_provider = data_dir_provider
        self._bus: EventBus | None = services.try_get("event_bus")
        self._runner.scrape_finished.connect(self._on_scrape_finished)  # type: ignore

    # ------------------------------------------------------------------
    def _on_scrape_finished(
        self, result: dict
    ):  # pragma: no cover - Qt signal wiring minimal logic
        data_dir = self._data_dir_provider()
        conn: sqlite3.Connection | None = services.try_get("sqlite_conn")
        if conn is None:
            if self._bus:
                self._bus.publish(
                    GUIEvent.ERROR_OCCURRED,
                    payload={"source": "post_scrape_ingest", "error": "Missing sqlite_conn"},
                )
            return
        coordinator = IngestionCoordinator(base_dir=data_dir, conn=conn, event_bus=self._bus)
        summary = coordinator.run()
        # IngestionCoordinator already emits DATA_REFRESHED; we can optionally also publish a completed event for UI to pick up ingestion summary specifically.
        if self._bus:
            self._bus.publish(GUIEvent.DATA_REFRESH_COMPLETED, payload={"ingestion": summary})
        # Auto-open Ingestion Lab logic (Milestone 7.10.61): if no rule set versions exist yet
        # and new HTML assets were discovered (processed_files > 0) we signal for the lab to open.
        try:
            if IngestionLabPanel is not None:
                rule_store = services.try_get("rule_version_store")
                has_rules = bool(rule_store and getattr(rule_store, "latest_version", None))
                if (not has_rules) and summary.processed_files > 0:
                    # Publish a dedicated event consumers (MainWindow) can handle to open the panel.
                    if self._bus:
                        self._bus.publish(
                            "OPEN_INGESTION_LAB",
                            {
                                "reason": "auto_open_first_html",
                                "processed_files": summary.processed_files,
                            },
                        )
        except Exception:  # pragma: no cover - non-fatal
            pass
