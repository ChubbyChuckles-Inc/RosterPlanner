"""Telemetry Service (Milestone 7.10.51)

Provides lightweight, opt-in counters for Ingestion Lab interactions.

Scope (initial):
    - preview_runs: number of preview actions (single or batch)
    - applied_runs: number of successful apply actions
    - total_preview_time_ms: cumulative elapsed time of previews

Average parse/preview time can be derived via helper. Service is designed to be
cheap and testable; it avoids any async/threading complexity. Persistence is
out-of-scope for this milestone (in-memory only; could later flush to SQLite or
JSON if a debug flag is enabled at shutdown).

Usage:
    from gui.services.telemetry_service import TelemetryService
    TelemetryService.instance.record_preview(42.5)

Opt-In: The service only records if the debug flag `INGESTION_TELEMETRY_ENABLED`
environment variable is truthy ("1", "true", "yes"). This avoids production
overhead unless explicitly enabled or toggled in tests.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import ClassVar, Dict, Any


def _env_truthy(val: str | None) -> bool:
    if not val:
        return False
    return val.lower() in {"1", "true", "yes", "on"}


@dataclass
class TelemetryService:
    """In-memory ingestion telemetry counters."""

    instance: ClassVar["TelemetryService"]

    enabled: bool = False
    preview_runs: int = 0
    applied_runs: int = 0
    total_preview_time_ms: float = 0.0

    def __post_init__(self) -> None:  # pragma: no cover - trivial branch
        # Initialize enabled state from env if not explicitly set
        if not self.enabled:
            self.enabled = _env_truthy(os.environ.get("INGESTION_TELEMETRY_ENABLED"))

    # Recording -------------------------------------------------------
    def record_preview(self, elapsed_ms: float) -> None:
        if not self.enabled:
            return
        self.preview_runs += 1
        self.total_preview_time_ms += max(0.0, float(elapsed_ms))

    def record_apply(self) -> None:
        if not self.enabled:
            return
        self.applied_runs += 1

    # Derived metrics -------------------------------------------------
    def average_preview_ms(self) -> float:
        if self.preview_runs == 0:
            return 0.0
        return self.total_preview_time_ms / self.preview_runs

    # Snapshot --------------------------------------------------------
    def snapshot(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "preview_runs": self.preview_runs,
            "applied_runs": self.applied_runs,
            "total_preview_time_ms": round(self.total_preview_time_ms, 3),
            "average_preview_ms": round(self.average_preview_ms(), 3),
        }


# Singleton instance
TelemetryService.instance = TelemetryService()
