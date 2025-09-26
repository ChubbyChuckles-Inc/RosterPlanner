"""Rule Set Versioning (Milestone 7.10.33)

Provides a lightweight persistence layer for versioned ingestion rule sets.

Scope (initial milestone):
 - Store each distinct rules payload (JSON-serializable mapping) as a new version
   with an auto-incremented version number starting at 1.
 - Skip creating a new version if the hash of the payload matches the latest.
 - Allow listing versions and retrieving a specific version's JSON text.
 - Provide helper to compute previous version for rollback functionality.

Future extensions (later milestones):
 - Attach author / user id metadata
 - Store human-readable change notes / commit messages
 - Diff generation utilities (field-level changes between versions)
 - Garbage collection / pruning policy
 - Export / import bundles for sharing between environments

Design Notes:
 - Uses the same SQLite connection provided via the service locator (key: 'sqlite_conn').
 - Table schema kept minimal; rules_json stored as TEXT exactly as provided to preserve formatting.
 - Hash is SHA1 of a stable representation (sorted items repr) truncated to 12 chars for brevity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Mapping, Any
import sqlite3
import hashlib

__all__ = [
    "RuleVersionEntry",
    "RuleSetVersionStore",
]


def _hash_payload(payload: Mapping[str, Any]) -> str:
    try:
        items = sorted(payload.items())
    except Exception:  # pragma: no cover - fallback path
        return hashlib.sha1(repr(payload).encode("utf-8", "ignore")).hexdigest()[:12]
    return hashlib.sha1(repr(items).encode("utf-8", "ignore")).hexdigest()[:12]


@dataclass
class RuleVersionEntry:
    version_num: int
    rules_hash: str
    rules_json: str
    created_at: str


class RuleSetVersionStore:
    """Persistence for versioned rule sets.

    Parameters
    ----------
    conn : sqlite3.Connection
        SQLite connection used for storage (caller manages lifecycle).
    table : str
        Table name (default: rule_set_versions) to allow namespacing in advanced scenarios.
    """

    def __init__(self, conn: sqlite3.Connection, table: str = "rule_set_versions") -> None:
        self._c = conn
        self._table = table
        self._ensure()

    # ------------------------------------------------------------------
    def _ensure(self) -> None:
        self._c.execute(
            f"CREATE TABLE IF NOT EXISTS {self._table}("  # nosec B608 - table name controlled by code
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"  # noqa: E231
            "version_num INTEGER NOT NULL,"  # noqa: E231
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"  # noqa: E231
            "rules_hash TEXT NOT NULL,"  # noqa: E231
            "rules_json TEXT NOT NULL,"  # noqa: E231
            "UNIQUE(version_num)"  # ensure monotonic unique numbering
            ")"
        )
        self._c.commit()

    # ------------------------------------------------------------------
    def latest(self) -> Optional[RuleVersionEntry]:
        cur = self._c.execute(
            f"SELECT version_num, rules_hash, rules_json, created_at FROM {self._table} ORDER BY version_num DESC LIMIT 1"
        )
        row = cur.fetchone()
        if not row:
            return None
        return RuleVersionEntry(
            version_num=int(row[0]),
            rules_hash=str(row[1]),
            rules_json=str(row[2]),
            created_at=str(row[3]),
        )

    # ------------------------------------------------------------------
    def save_version(self, payload: Mapping[str, Any], raw_json: str) -> int:
        """Persist a new version if payload differs from latest.

        Returns the version number (existing or newly created).
        """
        h = _hash_payload(payload)
        latest = self.latest()
        if latest and latest.rules_hash == h:
            return latest.version_num
        next_ver = 1 if latest is None else latest.version_num + 1
        self._c.execute(
            f"INSERT INTO {self._table}(version_num, rules_hash, rules_json) VALUES(?,?,?)",
            (next_ver, h, raw_json),
        )
        self._c.commit()
        return next_ver

    # ------------------------------------------------------------------
    def list_versions(self) -> List[RuleVersionEntry]:
        cur = self._c.execute(
            f"SELECT version_num, rules_hash, rules_json, created_at FROM {self._table} ORDER BY version_num DESC"
        )
        return [
            RuleVersionEntry(
                version_num=int(r[0]),
                rules_hash=str(r[1]),
                rules_json=str(r[2]),
                created_at=str(r[3]),
            )
            for r in cur.fetchall()
        ]

    # ------------------------------------------------------------------
    def get(self, version_num: int) -> Optional[RuleVersionEntry]:
        cur = self._c.execute(
            f"SELECT version_num, rules_hash, rules_json, created_at FROM {self._table} WHERE version_num=?",
            (version_num,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return RuleVersionEntry(
            version_num=int(row[0]),
            rules_hash=str(row[1]),
            rules_json=str(row[2]),
            created_at=str(row[3]),
        )

    # ------------------------------------------------------------------
    def previous_version(self, current_version: int) -> Optional[RuleVersionEntry]:
        if current_version <= 1:
            return None
        return self.get(current_version - 1)

    # ------------------------------------------------------------------
    def rollback_to_previous(self) -> Optional[str]:
        """Return JSON text for previous version (does not modify DB)."""
        latest = self.latest()
        if not latest:
            return None
        prev = self.previous_version(latest.version_num)
        if not prev:
            return None
        return prev.rules_json
