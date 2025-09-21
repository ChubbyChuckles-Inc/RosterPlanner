"""Offline-friendly icon & font asset caching (Milestone 0.33).

Goals:
- Track registered assets (icons, fonts) by stable identifier (stem of path unless overridden).
- Compute SHA256 hash of file bytes to detect changes.
- Provide version bump on re-registration when content hash changes.
- Persist / load a lightweight manifest (JSON) for future cold start optimization (optional).

This module is GUI-toolkit agnostic; integration layer will map IDs to actual
QIcon/QFont loading later. A future enhancement may add LRU eviction or memory
budget enforcement.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Optional, Iterable, Mapping, List
import hashlib
import json

__all__ = [
    "AssetCacheEntry",
    "register_asset",
    "get_asset",
    "list_assets",
    "load_manifest",
    "save_manifest",
    "compute_file_hash",
    "clear_assets",
]

_SUPPORTED_TYPES = {"icon", "font"}


@dataclass(frozen=True)
class AssetCacheEntry:
    id: str
    path: str
    type: str  # 'icon' | 'font'
    sha256: str
    version: int = 1


_registry: Dict[str, AssetCacheEntry] = {}


def compute_file_hash(path: str | Path) -> str:
    p = Path(path)
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"Asset file not found: {p}")
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def register_asset(
    path: str | Path, *, id: Optional[str] = None, type: str = "icon"
) -> AssetCacheEntry:
    if type not in _SUPPORTED_TYPES:
        raise ValueError(f"Unsupported asset type: {type}")
    p = Path(path)
    file_hash = compute_file_hash(p)
    asset_id = id or p.stem
    existing = _registry.get(asset_id)
    if existing:
        # If hash changed, increment version.
        if existing.sha256 != file_hash or existing.path != str(p):
            new_entry = AssetCacheEntry(
                id=asset_id,
                path=str(p),
                type=type,
                sha256=file_hash,
                version=existing.version + 1,
            )
            _registry[asset_id] = new_entry
            return new_entry
        return existing
    entry = AssetCacheEntry(id=asset_id, path=str(p), type=type, sha256=file_hash, version=1)
    _registry[asset_id] = entry
    return entry


def get_asset(asset_id: str) -> AssetCacheEntry:
    return _registry[asset_id]


def list_assets() -> Iterable[AssetCacheEntry]:
    return list(_registry.values())


def clear_assets() -> None:
    _registry.clear()


# Manifest -----------------------------------------------------------------
MANIFEST_VERSION = 1


def save_manifest(path: str | Path) -> None:
    data = {
        "version": MANIFEST_VERSION,
        "assets": [asdict(e) for e in _registry.values()],
    }
    p = Path(path)
    with p.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_manifest(path: str | Path) -> int:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Manifest not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("version") != MANIFEST_VERSION:
        # Return 0 to indicate incompatible; caller may choose to rebuild.
        return 0
    loaded: List[AssetCacheEntry] = []
    for obj in data.get("assets", []):
        try:
            entry = AssetCacheEntry(
                id=obj["id"],
                path=obj["path"],
                type=obj["type"],
                sha256=obj["sha256"],
                version=int(obj.get("version", 1)),
            )
            loaded.append(entry)
        except Exception:  # noqa: BLE001 - skip malformed
            continue
    _registry.update({e.id: e for e in loaded})
    return len(loaded)
