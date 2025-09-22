"""Layout persistence service (Milestone 2.3).

Provides simple versioned save/restore of QMainWindow geometry + dock state.
Uses a JSON sidecar file (binary state hex-encoded) to allow future schema
migration and inspection.

Features:
 - Version tag to detect invalid / legacy layouts
 - save_layout(name) / load_layout(name) APIs
 - Automatic directory creation
 - Graceful fallback on errors (returns False)

Future milestones (2.3.1 / 2.3.2) can build on this by adding named profiles
and automatic migration logic.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Any, Dict
import json
import os
import base64

try:  # Optional imports (tests may skip without Qt)
    from PyQt6.QtWidgets import QMainWindow
except Exception:  # pragma: no cover
    QMainWindow = object  # type: ignore

__all__ = ["LayoutPersistenceService", "LayoutPayload"]

LAYOUT_VERSION = 1  # increment when structure semantics change


@dataclass
class LayoutPayload:
    version: int
    geometry_b64: str
    state_b64: str

    @classmethod
    def from_window(cls, window: QMainWindow) -> "LayoutPayload":  # type: ignore[name-defined]
        geometry = window.saveGeometry()
        state = window.saveState()
        return cls(
            version=LAYOUT_VERSION,
            geometry_b64=base64.b64encode(bytes(geometry)).decode("ascii"),
            state_b64=base64.b64encode(bytes(state)).decode("ascii"),
        )

    def apply_to(self, window: QMainWindow) -> None:  # type: ignore[name-defined]
        from PyQt6.QtCore import QByteArray  # local import

        window.restoreGeometry(QByteArray(base64.b64decode(self.geometry_b64)))
        window.restoreState(QByteArray(base64.b64decode(self.state_b64)))


class LayoutPersistenceService:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    # Internal helpers ----------------------------------------------
    def _path_for(self, name: str) -> str:
        return os.path.join(self.base_dir, f"layout_{name}.json")

    def _read_payload(self, path: str) -> Optional[LayoutPayload]:
        """Attempt to read a layout payload.

        Returns None if file missing OR if version mismatch / invalid.
        (Migration logic handled in load_layout.)
        """
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            if obj.get("version") != LAYOUT_VERSION:
                return None
            return LayoutPayload(
                version=obj["version"],
                geometry_b64=obj["geometry_b64"],
                state_b64=obj["state_b64"],
            )
        except Exception:
            return None

    def _backup_and_invalidate(self, path: str, suffix: str) -> None:
        """Rename an invalid / legacy layout file for migration purposes.

        Best-effort; failures are swallowed.
        """
        if not os.path.exists(path):  # nothing to do
            return
        try:
            base = os.path.basename(path)
            new_name = base + suffix
            new_path = os.path.join(os.path.dirname(path), new_name)
            # Avoid overwriting an existing backup; append numeric if needed
            if os.path.exists(new_path):
                i = 1
                while os.path.exists(new_path + f".{i}") and i < 10:
                    i += 1
                new_path = new_path + f".{i}"
            os.replace(path, new_path)
        except Exception:
            pass

    # Public API ----------------------------------------------------
    def save_layout(self, name: str, window: QMainWindow) -> bool:  # type: ignore[name-defined]
        path = self._path_for(name)
        try:
            payload = LayoutPayload.from_window(window)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload.__dict__, f, indent=2)
            return True
        except Exception:
            return False

    def load_layout(self, name: str, window: QMainWindow) -> bool:  # type: ignore[name-defined]
        path = self._path_for(name)
        payload = self._read_payload(path)
        if not payload:
            # Determine if we need to migrate: if file exists but invalid version/corrupt
            if os.path.exists(path):
                # Attempt to read raw JSON to learn version for suffix; ignore errors
                suffix = ".bak"
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        obj = json.load(f)
                    old_ver = obj.get("version")
                    if isinstance(old_ver, int) and old_ver != LAYOUT_VERSION:
                        suffix = f".v{old_ver}.bak"
                except Exception:
                    suffix = ".corrupt.bak"
                self._backup_and_invalidate(path, suffix)
            return False
        try:
            payload.apply_to(window)
            return True
        except Exception:
            # Corrupt state content; backup and signal failure
            self._backup_and_invalidate(path, ".applyerr.bak")
            return False

    def reset_layout(self, name: str) -> bool:
        """Delete a stored layout file if it exists.

        Returns True if deleted, False if absent or on failure.
        """
        path = self._path_for(name)
        if not os.path.exists(path):
            return False
        try:
            os.remove(path)
            return True
        except Exception:
            return False
