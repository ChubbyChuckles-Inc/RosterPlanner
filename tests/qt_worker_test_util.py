"""Test utility helpers for running Qt-based workers with deterministic timeouts.

Centralizes the event loop execution pattern so we avoid copy/pasted 9s
timeouts that can accumulate and make the suite appear hung. A hard failure
is raised if the worker does not finish within the allotted time, making
the failure visible instead of silently quitting the loop with no result.
"""

from __future__ import annotations

from typing import Tuple, Type, Any
from PyQt6.QtCore import QCoreApplication, QTimer


def run_qt_worker(
    worker_cls: Type[Any], *args, timeout_ms: int = 2500, **kwargs
) -> Tuple[Any, str]:
    """Run a QRunnable/QThread-like worker class until finished or timeout.

    Parameters:
        worker_cls: Class implementing .start() and .finished signal (teams, error)
        timeout_ms: Maximum time to allow the event loop to run.
    Returns:
        (teams, error) tuple as emitted by the worker.
    Raises:
        TimeoutError if the worker fails to finish in time.
    """
    app = QCoreApplication.instance() or QCoreApplication([])  # type: ignore
    result_container = {"done": False, "teams": None, "error": ""}
    worker = worker_cls(*args, **kwargs)

    def _finished(teams, error):  # type: ignore
        result_container["teams"] = teams
        result_container["error"] = error
        result_container["done"] = True
        app.quit()

    worker.finished.connect(_finished)  # type: ignore
    worker.start()
    # Hard timeout enforcement
    QTimer.singleShot(timeout_ms, app.quit)  # type: ignore
    app.exec()  # type: ignore
    if not result_container["done"]:
        raise TimeoutError(
            f"Worker {worker_cls.__name__} did not finish within {timeout_ms}ms during test"
        )
    return result_container["teams"], result_container["error"]
