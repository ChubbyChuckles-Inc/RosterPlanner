"""ScrapeRunner service (GUI integration for scraping pipeline).

Provides an asynchronous wrapper around `services.pipeline.run_full` so the
GUI can trigger a full scrape without blocking the UI thread. Emits progress
lightly (placeholder) and completion signals.
"""

from __future__ import annotations
from typing import Callable, Optional, Any
from PyQt6.QtCore import QObject, QThread, pyqtSignal


class ScrapeWorker(QThread):  # pragma: no cover - thread orchestration
    finished_ok = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(
        self, club_id: int, season: int | None, data_dir: str, runner: Callable[..., dict]
    ):
        super().__init__()
        self._club_id = club_id
        self._season = season
        self._data_dir = data_dir
        self._runner = runner

    def run(self):  # noqa: D401
        try:
            result = self._runner(self._club_id, season=self._season, data_dir=self._data_dir)
            self.finished_ok.emit(result)
        except Exception as e:  # pragma: no cover - defensive
            self.failed.emit(str(e))


class ScrapeRunner(QObject):
    """Facade owning a worker thread instance for a single scrape invocation."""

    scrape_started = pyqtSignal()
    scrape_finished = pyqtSignal(dict)
    scrape_failed = pyqtSignal(str)

    def __init__(self, pipeline_func: Optional[Callable[..., dict]] = None):
        super().__init__()
        if pipeline_func is None:
            from services import pipeline  # lazy import to avoid GUI startup penalty

            pipeline_func = pipeline.run_full
        self._pipeline = pipeline_func
        self._worker: ScrapeWorker | None = None

    def is_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def start(self, club_id: int, season: int | None, data_dir: str):
        if self.is_running():  # pragma: no cover - guard
            return
        self._worker = ScrapeWorker(club_id, season, data_dir, self._pipeline)
        self._worker.finished_ok.connect(self._on_ok)  # type: ignore
        self._worker.failed.connect(self._on_failed)  # type: ignore
        self.scrape_started.emit()
        self._worker.start()

    def _on_ok(self, result: dict):  # pragma: no cover - signal path
        self.scrape_finished.emit(result)
        self._cleanup()

    def _on_failed(self, msg: str):  # pragma: no cover - signal path
        self.scrape_failed.emit(msg)
        self._cleanup()

    def _cleanup(self):  # pragma: no cover - thread lifecycle
        if self._worker:
            self._worker.wait(100)
        self._worker = None


__all__ = ["ScrapeRunner"]
