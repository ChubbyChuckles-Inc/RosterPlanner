"""Diagnostics utilities (Milestone 1.9.2).

Provides helpers to build a structured crash reproduction snippet aggregating:
 - Environment (python version, platform)
 - Recent uncaught errors (from ErrorHandlingService)
 - Deduplicated error summary
 - Recent log records (from LoggingService)
 - Recent events (from EventBus tracing if enabled)

Design Principles:
 - Pure functions where possible for testability
 - Avoid importing heavyweight GUI modules
 - Limit sizes (caps) to keep snippet manageable for issue reports
"""

from __future__ import annotations

from typing import Any, Dict, Sequence
import platform
import sys
import json
from datetime import datetime

__all__ = ["generate_crash_snippet", "format_crash_snippet_text"]


def _serialize_error(err) -> Dict[str, Any]:  # pragma: no cover - simple
    return {
        "type": err.exc_type.__name__,
        "message": str(err.exc_value),
        "iso_time": err.iso_time,
        "thread": err.thread_name,
    }


def generate_crash_snippet(
    *,
    error_service: Any,
    logging_service: Any | None = None,
    event_bus: Any | None = None,
    max_errors: int = 5,
    max_logs: int = 50,
    max_events: int = 30,
) -> Dict[str, Any]:
    """Assemble structured crash reproduction snippet.

    Parameters
    ----------
    error_service: ErrorHandlingService
        Source of uncaught errors & dedup groups.
    logging_service: LoggingService | None
        Optional log provider (expects .recent() -> list[LogRecordLike]).
    event_bus: EventBus | None
        Optional event bus for recent traced events (expects .recent_trace_entries()).
    max_errors, max_logs, max_events: int
        Upper bounds for included list sizes to avoid oversized outputs.
    """

    now_iso = datetime.utcnow().isoformat() + "Z"
    recent_errors = error_service.recent_errors()[-max_errors:]
    dedup_groups = getattr(error_service, "dedup_entries", lambda: [])()

    logs: list[dict[str, Any]] = []
    if logging_service is not None:
        for rec in logging_service.recent()[-max_logs:]:  # assumes list-like of LogRecord dataclass
            logs.append(
                {
                    "level": rec.level,
                    "name": rec.name,
                    "message": rec.message,
                    "created": rec.created,
                }
            )

    events: list[dict[str, Any]] = []
    if event_bus is not None and getattr(event_bus, "tracing_enabled", False):
        for te in event_bus.recent_trace_entries()[-max_events:]:
            # TraceEntry defined with (name, timestamp, payload_summary?) actual dataclass fields: name, timestamp, payload_summary OR summary? adapt dynamically
            summary_val = getattr(te, "payload_summary", None)
            if summary_val is None:
                summary_val = getattr(te, "summary", "")
            events.append(
                {
                    "name": te.name,
                    "timestamp": te.timestamp,
                    "summary": summary_val,
                }
            )

    snippet = {
        "generated_at": now_iso,
        "environment": {
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "implementation": platform.python_implementation(),
        },
        "errors": [_serialize_error(e) for e in recent_errors],
        "error_dedup": [
            {
                "type": g.first.exc_type.__name__,
                "message": str(g.first.exc_value),
                "count": g.count,
                "first_time": g.first.iso_time,
                "last_time": datetime.utcfromtimestamp(g.last_timestamp).isoformat() + "Z",
            }
            for g in dedup_groups
        ],
        "logs": logs,
        "events": events,
        "limits": {"max_errors": max_errors, "max_logs": max_logs, "max_events": max_events},
        "schema_version": 1,
    }
    return snippet


def format_crash_snippet_text(snippet: Dict[str, Any]) -> str:
    """Return a human-friendly text block (JSON + short summary header)."""
    parts = [
        f"Crash Reproduction Snippet (generated {snippet['generated_at']})",
        "Summary:",
        f"  Errors: {len(snippet['errors'])} (groups: {len(snippet['error_dedup'])})",
        f"  Logs: {len(snippet['logs'])}  Events: {len(snippet['events'])}",
        "JSON Payload:",
        json.dumps(snippet, sort_keys=True, indent=2),
    ]
    return "\n".join(parts)
