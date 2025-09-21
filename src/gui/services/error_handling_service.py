"""Global error handling service (Milestone 1.9 - skeleton).

Captures uncaught exceptions via ``sys.excepthook`` (and ``threading.excepthook``
when available) so the application can surface diagnostics to the user and
retain a short history for inspection/export.

Design Goals (phase 1 skeleton):
 - Lightweight: no heavy imports at module import time.
 - Non-intrusive: if install() is never called, no global state mutated.
 - Testable: expose a ``handle_exception`` method used by hooks and tests.
 - Ring buffer storage (default capacity 20) of structured ``ErrorRecord``.

Deferred (later subtasks in milestone):
 - Integration with LoggingService (structured log emission)
 - EventBus signal (UNCAUGHT_EXCEPTION)
 - User-facing dialog wiring (Qt layer)
 - Export utilities (JSON / text formatting)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Deque, List, Optional, Callable, Any
from collections import deque
import sys
import threading
import traceback

__all__ = [
    "ErrorRecord",
    "ErrorHandlingService",
]


@dataclass(frozen=True)
class ErrorRecord:
    """Structured capture of an uncaught exception.

    Attributes
    ----------
    exc_type: type
        Exception class.
    exc_value: BaseException
        Exception instance.
    traceback_str: str
        Formatted traceback text.
    timestamp: float
        POSIX timestamp when handled.
    iso_time: str
        ISO 8601 timestamp (UTC) for ease of display / export.
    thread_name: str
        Name of the thread in which the exception occurred.
    """

    exc_type: type
    exc_value: BaseException
    traceback_str: str
    timestamp: float
    iso_time: str
    thread_name: str

    def summary(self, max_len: int = 120) -> str:  # pragma: no cover - trivial
        msg = f"{self.exc_type.__name__}: {self.exc_value}"
        return msg if len(msg) <= max_len else msg[: max_len - 3] + "..."


class ErrorHandlingService:
    """Installable global error hook manager.

    Usage
    -----
    svc = ErrorHandlingService()
    svc.install()
    ... run application ...
    svc.uninstall()  # restore previous hooks (optional on clean exit)

    Thread Safety
    -------------
    The ring buffer operations are cheap; GIL suffices for simple append.
    """

    def __init__(
        self, *, capacity: int = 20, logger: Any | None = None, event_bus: Any | None = None
    ) -> None:
        self._capacity = max(1, capacity)
        self._errors: Deque[ErrorRecord] = deque(maxlen=self._capacity)
        self._installed: bool = False
        self._prev_sys_hook = None  # type: ignore[assignment]
        self._prev_threading_hook = None  # type: ignore[assignment]
        self._logger = logger  # expected interface subset: .error(msg)
        self._event_bus = event_bus  # expected subset: .publish(name, payload)

    # ------------------------------------------------------------------
    # Installation / Removal
    # ------------------------------------------------------------------
    def install(self) -> None:
        if self._installed:
            return
        self._prev_sys_hook = sys.excepthook
        sys.excepthook = self._sys_hook  # type: ignore[assignment]
        # Python 3.8+: threading.excepthook attribute
        if hasattr(threading, "excepthook"):
            self._prev_threading_hook = threading.excepthook  # type: ignore[attr-defined]
            threading.excepthook = self._thread_hook  # type: ignore[attr-defined]
        self._installed = True

    def uninstall(self) -> None:
        if not self._installed:
            return
        if self._prev_sys_hook is not None:
            sys.excepthook = self._prev_sys_hook  # type: ignore[assignment]
        if hasattr(threading, "excepthook") and self._prev_threading_hook is not None:
            threading.excepthook = self._prev_threading_hook  # type: ignore[attr-defined]
        self._installed = False

    # ------------------------------------------------------------------
    # Internal hook adapters
    # ------------------------------------------------------------------
    def _sys_hook(self, exc_type, exc_value, tb):  # pragma: no cover - delegate
        self.handle_exception(exc_type, exc_value, tb)
        # Delegate to previous to retain default stderr printing behavior
        if self._prev_sys_hook:
            try:
                self._prev_sys_hook(exc_type, exc_value, tb)
            except Exception:  # pragma: no cover - defensive
                pass

    def _thread_hook(self, args):  # pragma: no cover - delegate wrapper
        # threading.ExceptHookArgs structure: (exc_type, exc_value, exc_traceback, thread)
        self.handle_exception(args.exc_type, args.exc_value, args.exc_traceback, thread=args.thread)
        if self._prev_threading_hook:
            try:
                self._prev_threading_hook(args)
            except Exception:  # pragma: no cover
                pass

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------
    def handle_exception(
        self, exc_type, exc_value, tb, *, thread: Optional[threading.Thread] = None
    ) -> ErrorRecord:
        """Capture an uncaught exception and store an ``ErrorRecord``.

        Exposed publicly to allow tests (and future layers) to feed synthetic
        exceptions without altering global hooks.
        """
        trace_text = "".join(traceback.format_exception(exc_type, exc_value, tb))
        ts = datetime.utcnow().timestamp()
        record = ErrorRecord(
            exc_type=exc_type,
            exc_value=exc_value,
            traceback_str=trace_text,
            timestamp=ts,
            iso_time=datetime.utcfromtimestamp(ts).isoformat() + "Z",
            thread_name=(thread.name if thread else threading.current_thread().name),
        )
        self._errors.append(record)
        # Structured log emission (simple message for now)
        if self._logger is not None:
            try:  # pragma: no cover - defensive
                self._logger.error(
                    f"Uncaught exception ({record.thread_name}) {record.exc_type.__name__}: {record.exc_value}"
                )
            except Exception:
                pass
        if self._event_bus is not None:
            try:  # pragma: no cover - defensive
                from .event_bus import GUIEvent  # local import to avoid cycle at module import

                self._event_bus.publish(
                    GUIEvent.UNCAUGHT_EXCEPTION,
                    {
                        "type": record.exc_type.__name__,
                        "message": str(record.exc_value),
                        "thread": record.thread_name,
                        "iso_time": record.iso_time,
                    },
                )
            except Exception:
                pass
        return record

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def recent_errors(self) -> List[ErrorRecord]:
        return list(self._errors)

    @property
    def installed(self) -> bool:
        return self._installed

    def clear(self) -> None:
        self._errors.clear()
