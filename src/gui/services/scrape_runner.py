"""ScrapeRunner service (GUI integration for scraping pipeline).

Provides an asynchronous wrapper around `services.pipeline.run_full` so the
GUI can trigger a full scrape without blocking the UI thread. Emits progress
lightly (placeholder) and completion signals.
"""

from __future__ import annotations
from typing import Callable, Optional, Any, List, Tuple
from PyQt6.QtCore import QObject, QThread, pyqtSignal


class _CancelToken:
    def __init__(self):
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def is_cancelled(self):
        return self._cancelled


class ScrapeWorker(QThread):  # pragma: no cover - thread orchestration
    finished_ok = pyqtSignal(dict)
    failed = pyqtSignal(str)
    progress_event = pyqtSignal(str, dict)

    def __init__(
        self, club_id: int, season: int | None, data_dir: str, runner: Callable[..., dict]
    ):
        super().__init__()
        self._club_id = club_id
        self._season = season
        self._data_dir = data_dir
        self._runner = runner
        self._cancel_token = _CancelToken()

    def run(self):  # noqa: D401
        try:

            def _progress(event: str, payload: dict):
                self.progress_event.emit(event, payload)

            result = self._runner(
                self._club_id,
                season=self._season,
                data_dir=self._data_dir,
                progress=_progress,
                cancel_token=self._cancel_token,
            )
            self.finished_ok.emit(result)
        except Exception as e:  # pragma: no cover - defensive
            self.failed.emit(str(e))

    def cancel(self):  # pragma: no cover - external call
        self._cancel_token.cancel()


class ScrapeRunner(QObject):
    """Facade owning a worker thread instance for a single scrape invocation."""

    scrape_started = pyqtSignal()
    scrape_finished = pyqtSignal(dict)
    scrape_failed = pyqtSignal(str)
    scrape_progress = pyqtSignal(str, dict)  # (event, payload)
    scrape_cancelled = pyqtSignal()

    def __init__(self, pipeline_func: Optional[Callable[..., dict]] = None):
        super().__init__()
        if pipeline_func is None:
            from services import pipeline  # lazy import to avoid GUI startup penalty

            pipeline_func = pipeline.run_full
        self._pipeline = pipeline_func
        self._worker: ScrapeWorker | None = None
        self._queue: List[Tuple[int, int | None, str]] = []
        self._pause = False

    # Queue management -------------------------------------------------
    def queued_job_count(self) -> int:
        return len(self._queue)

    def is_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def start(self, club_id: int, season: int | None, data_dir: str):
        if self.is_running():  # already running; queue next
            self._queue.append((club_id, season, data_dir))
            self.scrape_progress.emit("queue_update", {"queued": len(self._queue)})  # type: ignore
            return
        # Build pause token exposing is_paused()
        class _PauseToken:
            def __init__(self, runner: 'ScrapeRunner'):
                self._runner = runner

            def is_paused(self):  # pragma: no cover
                return self._runner._pause

        pause_token = _PauseToken(self)

        # Wrap pipeline to inject pause_token
        def _runner_wrapper(club_id: int, season: int | None, data_dir: str, **kwargs):
            kwargs.setdefault("pause_token", pause_token)
            return self._pipeline(club_id, season=season, data_dir=data_dir, **kwargs)

        self._worker = ScrapeWorker(club_id, season, data_dir, _runner_wrapper)
        self._worker.finished_ok.connect(self._on_ok)  # type: ignore
        self._worker.failed.connect(self._on_failed)  # type: ignore
        self._worker.progress_event.connect(self._on_progress)  # type: ignore
        self.scrape_started.emit()
        self._worker.start()

    def cancel(self):  # pragma: no cover
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self.scrape_cancelled.emit()
        # Clear queued jobs on cancel
        self._queue.clear()
        self.scrape_progress.emit("queue_update", {"queued": 0})  # type: ignore

    # Pause / Resume ---------------------------------------------------
    def pause(self):  # pragma: no cover
        self._pause = True
        self.scrape_progress.emit("paused", {})  # type: ignore

    def resume(self):  # pragma: no cover
        self._pause = False
        self.scrape_progress.emit("resumed", {})  # type: ignore

    def _on_ok(self, result: dict):  # pragma: no cover - signal path
        self.scrape_finished.emit(result)
        self._cleanup()
        # Dequeue next job if present
        if self._queue:
            next_club, next_season, next_dir = self._queue.pop(0)
            self.scrape_progress.emit("queue_update", {"queued": len(self._queue)})  # type: ignore
            self.start(next_club, next_season, next_dir)

    def _on_failed(self, msg: str):  # pragma: no cover - signal path
        self.scrape_failed.emit(msg)
        self._cleanup()
        # On failure, keep queued jobs (user can retry)

    def _cleanup(self):  # pragma: no cover - thread lifecycle
        if self._worker:
            self._worker.wait(100)
        self._worker = None

    def _on_progress(self, event: str, payload: dict):  # pragma: no cover
        self.scrape_progress.emit(event, payload)


__all__ = ["ScrapeRunner"]
