"""Hash impact data structures for the ingestion lab panel."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["HashImpactResult"]


@dataclass
class HashImpactResult:
    """Result container for hash impact preview (Milestone 7.10.22).

    Attributes
    ----------
    updated: list[str]
        Existing provenance entries whose current file hash differs (would be re-ingested).
    unchanged: list[str]
        Files whose hash matches provenance (eligible for cached skip path).
    new: list[str]
        Files present on disk but absent from provenance table (first-time ingest).
    missing: list[str]
        Provenance entries referencing files no longer present on disk (stale rows).
    """

    updated: list[str]
    unchanged: list[str]
    new: list[str]
    missing: list[str]

    def summary(self) -> str:  # pragma: no cover - trivial
        """Return a human readable summary of the hash impact result."""

        return (
            f"Updated {len(self.updated)} | Unchanged {len(self.unchanged)} | "
            f"New {len(self.new)} | Missing {len(self.missing)}"
        )
