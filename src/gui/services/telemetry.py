"""Simple telemetry counters service for debug metrics.

Provides a minimal, testable counters service intended to be used behind a
debug flag. It supports incrementing named counters, retrieving snapshots,
and resetting counters. This is suitable to implement ingest telemetry
(parsed_count, skipped_count) behind a feature flag.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class TelemetryService:
    """A simple telemetry counters service.

    Attributes:
        enabled: If False, operations are no-ops.
        _counters: Internal mapping of counter name to integer value.
    """

    enabled: bool = False
    _counters: Dict[str, int] = field(default_factory=dict)

    def increment(self, name: str, delta: int = 1) -> None:
        """Increment counter `name` by `delta` (no-op if disabled)."""
        if not self.enabled:
            return
        if delta == 0:
            return
        self._counters[name] = self._counters.get(name, 0) + int(delta)

    def get(self, name: str) -> int:
        """Get the current value of counter `name` (0 if missing)."""
        return int(self._counters.get(name, 0))

    def snapshot(self) -> Dict[str, int]:
        """Return a shallow copy of counters."""
        return dict(self._counters)

    def reset(self) -> None:
        """Reset all counters to empty mapping."""
        self._counters.clear()
