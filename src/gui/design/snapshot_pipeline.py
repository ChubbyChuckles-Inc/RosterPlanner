"""Continuous design snapshot pipeline utilities (Milestone 0.29).

This module provides primitives for capturing deterministic image hashes of
rendered widgets or surfaces to enable nightly regression detection. The full
pipeline (scheduling, storage, diff UI) will be implemented incrementally; here
we focus on hash computation and a pluggable capture abstraction.

Design Goals
------------
- Keep capture decoupled from PyQt6 until integration phase: the capture input is
  bytes-like (e.g., PNG) rather than a QWidget directly for testability.
- Deterministic hashing via SHA256 of raw bytes.
- Lightweight record object to store metadata for future diffing.

Future Extensions (not implemented yet):
- Automatic diffing and highlighting changed regions.
- Persisting historical baseline sets per component variant.
- Scheduling (cron-like) using an app-level job scheduler.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from datetime import datetime
from typing import Optional

__all__ = [
    "SnapshotRecord",
    "compute_image_hash",
    "capture_bytes_placeholder",
]


@dataclass(frozen=True)
class SnapshotRecord:
    component: str
    variant: str
    hash: str
    captured_at: datetime
    notes: Optional[str] = None


def compute_image_hash(data: bytes) -> str:
    """Compute a stable SHA256 hex digest for image bytes."""
    return hashlib.sha256(data).hexdigest()


def capture_bytes_placeholder(width: int = 1, height: int = 1, color: int = 0xFFFFFFFF) -> bytes:
    """Generate a tiny RGBA PNG-like placeholder sequence.

    This is NOT a full PNG encoder—just a deterministic byte pattern suitable
    for hashing tests. Real capture will replace this with QPixmap/QImage ->
    PNG bytes extraction.
    """
    # Compose a simple header + pixel representation (not a valid PNG).
    header = b"SNAP" + width.to_bytes(2, "big") + height.to_bytes(2, "big")
    pixel = color.to_bytes(4, "big") * (width * height)
    return header + pixel
