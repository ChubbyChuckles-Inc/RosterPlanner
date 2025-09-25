"""Stats Cache Service (Milestone 6.7)

Provides lightweight in-memory caching for statistics computations with
hash-based invalidation driven by data freshness timestamps (scrape + ingest)
and optional explicit dependency keys.

Design Goals:
 - Avoid premature complexity: simple dict with composite key -> value.
 - Deterministic hash of inputs (sorted serialization) so order of lists does
   not affect cache hits.
 - Invalidate transparently when data freshness (last_ingest timestamp) changes.
 - Expose manual `invalidate(prefix=None)` for targeted eviction.
 - Thread-safety is not addressed yet (GUI single-thread usage expected; future
   background workers can wrap with a lock if needed).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
import json
import hashlib
from datetime import datetime

from .service_locator import services
from .data_freshness_service import DataFreshnessService

__all__ = ["StatsCacheService", "CacheEntry"]


@dataclass
class CacheEntry:
    value: Any
    created_at: datetime
    freshness_token: Optional[str]


def _stable_hash(obj: Any) -> str:
    try:
        # Convert to JSON with sorted keys for deterministic representation
        data = json.dumps(obj, sort_keys=True, default=str, separators=(",", ":"))
    except TypeError:
        # Fallback: string representation
        data = repr(obj)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


class StatsCacheService:
    """Simple statistics result cache with freshness-aware invalidation."""

    def __init__(self) -> None:
        self._store: Dict[str, CacheEntry] = {}
        self._last_freshness_token: Optional[str] = None

    # Public API -----------------------------------------------------------
    def get_or_compute(
        self,
        namespace: str,
        inputs: Any,
        compute_fn,
        include_freshness: bool = True,
    ) -> Any:
        """Return cached value for (namespace, inputs) or compute & cache.

        Args:
            namespace: Logical group (e.g. 'kpi.team_win_pct').
            inputs: Hashable (after stable serialization) inputs structure.
            compute_fn: Zero-arg callable computing value if cache miss.
            include_freshness: If True, embed last_ingest timestamp into key so cache
                automatically invalidates after new ingest. If False, caller must
                manually invalidate.
        """
        self._maybe_refresh_freshness_token()
        freshness = self._last_freshness_token if include_freshness else None
        key = self._make_key(namespace, inputs, freshness)
        entry = self._store.get(key)
        if entry is not None:
            return entry.value
        value = compute_fn()
        self._store[key] = CacheEntry(
            value=value, created_at=datetime.utcnow(), freshness_token=freshness
        )
        return value

    def invalidate(self, prefix: Optional[str] = None) -> int:
        """Invalidate cache entries.

        Args:
            prefix: If provided, only entries whose key starts with prefix are
                removed; otherwise all entries removed.
        Returns:
            Count of removed entries.
        """
        if prefix is None:
            removed = len(self._store)
            self._store.clear()
            return removed
        to_delete = [k for k in self._store if k.startswith(prefix)]
        for k in to_delete:
            del self._store[k]
        return len(to_delete)

    def stats(self) -> Dict[str, Any]:
        return {
            "entries": len(self._store),
            "freshness_token": self._last_freshness_token,
        }

    # Internal helpers -----------------------------------------------------
    def _make_key(self, namespace: str, inputs: Any, freshness: Optional[str]) -> str:
        parts = [namespace, _stable_hash(inputs)]
        if freshness:
            parts.append(freshness)
        return "|".join(parts)

    def _maybe_refresh_freshness_token(self) -> None:
        freshness = DataFreshnessService().current()
        # Use last_ingest iso timestamp as token; None stays None -> caller decides if included
        token = freshness.last_ingest.isoformat() if freshness.last_ingest else None
        if token != self._last_freshness_token:
            # Invalidate all entries bound to old freshness token
            if self._last_freshness_token is not None:
                self.invalidate()
            self._last_freshness_token = token
