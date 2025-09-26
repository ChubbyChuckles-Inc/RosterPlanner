"""RosterCacheService (Milestone 5.9.19)

Provides a simple in-memory Least-Recently-Used (LRU) cache for team
roster bundles to reduce repeated repository queries when users switch
between already opened teams. The cache is *session-scoped* (lives for
the QApplication lifetime) and intentionally lightweight:

Design Goals:
 - O(1) average insert / lookup / eviction using OrderedDict.
 - Size-bound (default 32 entries) to avoid unbounded memory growth.
 - Explicit `invalidate_team` and `clear` operations to respond to
   ingestion events or targeted data changes.
 - Type-hinted, testable, no PyQt dependencies (pure Python logic).

Invalidation Strategy:
 - Full clear invoked after a successful ingestion run (since player or
   match composition may have changed) via external wiring (e.g., an
   event bus subscriber). For now, TeamDataService exposes a helper to
   request invalidation through the service locator if the cache exists.

Thread Safety: Not thread-safe; access is expected from the GUI thread.
If background worker threads need to populate it in future, a simple
lock can be added.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, Optional

from gui.models import TeamRosterBundle

__all__ = ["RosterCacheService"]


@dataclass
class RosterCacheService:
    """A size-bound LRU cache for `TeamRosterBundle` instances.

    Parameters
    ----------
    capacity : int
        Maximum number of team bundles to retain. Inserting a new bundle
        beyond this capacity evicts the least-recently-used entry.
    """

    capacity: int = 32
    # Tracks the rule set version whose results currently populate the cache.
    # When a differing rule version is observed, the cache is cleared to avoid
    # serving stale roster bundles derived from older transformation rules.
    last_rule_version: int | None = None

    def __post_init__(self) -> None:  # pragma: no cover - trivial
        if self.capacity <= 0:
            self.capacity = 1
        self._store: "OrderedDict[str, TeamRosterBundle]" = OrderedDict()

    # Public API -------------------------------------------------
    def get(self, team_id: str) -> Optional[TeamRosterBundle]:
        """Retrieve a cached bundle if present and mark as recently used."""
        bundle = self._store.get(team_id)
        if bundle is not None:
            # Move to end (most recently used)
            self._store.move_to_end(team_id, last=True)
        return bundle

    def put(self, team_id: str, bundle: TeamRosterBundle) -> None:
        """Insert or update a bundle in the cache.

        Evicts the least recently used entry if size exceeds capacity.
        """
        if team_id in self._store:
            self._store.move_to_end(team_id, last=True)
            self._store[team_id] = bundle
        else:
            self._store[team_id] = bundle
            if len(self._store) > self.capacity:
                # popitem(last=False) pops LRU
                self._store.popitem(last=False)

    def invalidate_team(self, team_id: str) -> None:
        """Remove a single team from the cache if present."""
        self._store.pop(team_id, None)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._store.clear()

    # Rule version awareness -----------------------------------------------
    def ensure_rule_version(self, current: int | None) -> None:
        """Ensure the cache is aligned with the provided rule version.

        Behavior:
        - If current is None: no action (legacy / unknown rule context).
        - If last_rule_version is None and current provided: set it (first observation).
        - If last_rule_version differs from current: clear cache and update.
        """
        if current is None:
            return
        if self.last_rule_version is None:
            self.last_rule_version = current
            return
        if self.last_rule_version != current:
            # Invalidate all cached bundles produced under prior rule set.
            self.clear()
            self.last_rule_version = current

    def __len__(self) -> int:  # pragma: no cover - simple passthrough
        return len(self._store)

    # Introspection helpers (could support UI diagnostics) ------
    def keys(self) -> list[str]:  # pragma: no cover
        return list(self._store.keys())

    def snapshot(self) -> Dict[str, int]:  # pragma: no cover
        """Return a lightweight snapshot mapping team_id -> player_count."""
        return {k: len(v.players) for k, v in self._store.items()}
