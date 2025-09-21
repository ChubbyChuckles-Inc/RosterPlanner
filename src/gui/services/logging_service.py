"""Logging service (Milestone 1.8 initial implementation).

Provides an in-process logging handler capturing recent log records into a
ring buffer, emitting `GUIEvent.LOG_RECORD_ADDED` via EventBus for UI panels.

Design goals:
 - Headless testability (no Qt dependency here)
 - Filtering by level name substring or logger name
 - Capacity-bound ring buffer with O(1) append
 - Retrieval API returning lightweight serializable dicts
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from threading import RLock
from typing import Deque, Iterable, List, Optional

from .event_bus import EventBus, GUIEvent
from .service_locator import services

__all__ = [
    "LogEntry",
    "LoggingService",
    "get_logging_service",
]


@dataclass(frozen=True)
class LogEntry:
    level: str
    name: str
    message: str
    created: float
    pathname: str
    lineno: int


class _RingBufferHandler(logging.Handler):
    def __init__(self, svc: "LoggingService") -> None:
        super().__init__()
        self._svc = svc

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401
        self._svc._ingest_record(record)


class LoggingService:
    def __init__(self, capacity: int = 500) -> None:
        self._capacity = capacity
        self._lock = RLock()
        self._entries: Deque[LogEntry] = deque(maxlen=capacity)
        self._handler = _RingBufferHandler(self)
        self._handler.setLevel(logging.DEBUG)
        self._attached = False

    # Lifecycle --------------------------------------------------------
    def attach_root(self) -> None:
        if self._attached:
            return
        root = logging.getLogger()
        root.addHandler(self._handler)
        # Ensure we don't miss lower-severity records (preserve existing if already lower)
        if root.level > logging.DEBUG:
            root.setLevel(logging.DEBUG)
        self._attached = True

    def detach_root(self) -> None:
        if not self._attached:
            return
        logging.getLogger().removeHandler(self._handler)
        self._attached = False

    # Internal ingestion -----------------------------------------------
    def _ingest_record(self, record: logging.LogRecord) -> None:
        entry = LogEntry(
            level=record.levelname,
            name=record.name,
            message=record.getMessage(),
            created=record.created,
            pathname=record.pathname,
            lineno=record.lineno,
        )
        with self._lock:
            self._entries.append(entry)
        # Emit event (best-effort)
        try:
            bus = services.get_typed("event_bus", EventBus)
            bus.publish(
                GUIEvent.LOG_RECORD_ADDED,
                {
                    "level": entry.level,
                    "name": entry.name,
                    "message": entry.message[:120],
                    "created": entry.created,
                },
            )
        except Exception:  # pragma: no cover - silent if bus missing
            pass

    # Query ------------------------------------------------------------
    def recent(self, limit: Optional[int] = None) -> List[LogEntry]:
        with self._lock:
            data = list(self._entries)
        return data[-limit:] if limit is not None else data

    def filter(
        self, *, level: str | None = None, name_contains: str | None = None
    ) -> List[LogEntry]:
        entries = self.recent()
        out: List[LogEntry] = []
        for e in entries:
            if level and e.level != level:
                continue
            if name_contains and name_contains not in e.name:
                continue
            out.append(e)
        return out

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    # Export ------------------------------------------------------------
    def export_jsonl(
        self,
        path: str | None = None,
        *,
        level: str | None = None,
        name_contains: str | None = None,
        append: bool = False,
    ) -> int:
        """Export filtered log entries as JSON Lines.

        Returns number of lines written.
        """
        import json, os  # local import to keep module import light

        entries = self.filter(level=level, name_contains=name_contains)
        mode = "a" if append else "w"
        file_path = path or os.path.join(os.getcwd(), "logs.jsonl")
        with open(file_path, mode, encoding="utf-8") as f:
            for e in entries:
                f.write(
                    json.dumps(
                        {
                            "level": e.level,
                            "name": e.name,
                            "message": e.message,
                            "created": e.created,
                            "file": e.pathname,
                            "line": e.lineno,
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
        return len(entries)


def get_logging_service() -> LoggingService:
    return services.get_typed("logging_service", LoggingService)
