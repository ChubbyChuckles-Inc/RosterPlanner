"""Icon registry for managing SVG icon assets.

Responsibilities:
- Provide a central place to register and resolve icon names to file paths.
- Support plugin-time dynamic registration.
- Enforce simple validation (existence of file, naming rules).

Future extensions:
- Cached QIcon/QPixmap creation.
- Themed variants, multi-color layers.

Usage:
    from gui.design.icons import register_icon, get_icon_path
    register_icon("placeholder", Path("assets/icons/base/placeholder.svg"))
    path = get_icon_path("placeholder")
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from threading import RLock
from typing import Dict, Iterable, Optional

__all__ = [
    "IconDescriptor",
    "register_icon",
    "get_icon_path",
    "list_icons",
    "clear_icons",
    "compute_icon_hash",
    "get_icon_hash_map",
    "export_icon_hash_map",
]

# Base directory for built-in icons (relative to project root). Adjust if packaging changes.
_BASE_ICON_DIR = Path(__file__).resolve().parents[3] / "assets" / "icons" / "base"

_lock = RLock()
_registry: Dict[str, "IconDescriptor"] = {}


@dataclass
class IconDescriptor:
    name: str
    path: Path
    source: str = "core"  # 'core' or plugin name
    deprecated: bool = False

    def exists(self) -> bool:
        return self.path.is_file()


def _validate_name(name: str) -> None:
    if not name or name.strip() == "":
        raise ValueError("Icon name cannot be empty")
    if any(ch for ch in name if ch.lower() != ch):
        raise ValueError("Icon name must be lowercase (kebab-case)")
    # rudimentary kebab-case check
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789-_")
    if not set(name) <= allowed:
        raise ValueError(f"Icon name contains invalid characters: {name}")


def register_icon(name: str, path: Path, *, source: str = "core", override: bool = False) -> None:
    """Register an icon by name.

    Parameters
    ----------
    name: symbolic icon name (kebab-case)
    path: filesystem path to SVG file
    source: 'core' or plugin identifier
    override: allow replacement if an icon with the same name already exists
    """
    _validate_name(name)
    if not path.is_file():
        raise FileNotFoundError(f"Icon file not found: {path}")
    with _lock:
        if name in _registry and not override:
            raise KeyError(f"Icon already registered: {name}")
        _registry[name] = IconDescriptor(name=name, path=path, source=source)


def get_icon_path(name: str) -> Path:
    """Return the filesystem path for a registered icon.

    Raises KeyError if not registered.
    """
    with _lock:
        if name not in _registry:
            raise KeyError(f"Icon not registered: {name}")
        return _registry[name].path


def list_icons() -> Iterable[IconDescriptor]:
    with _lock:
        return list(_registry.values())


def clear_icons() -> None:
    with _lock:
        _registry.clear()


# ---------------------------------------------------------------------------
# Hashing / cache-busting (Milestone 1.7 asset pipeline primitive)
# ---------------------------------------------------------------------------
_hash_cache: Dict[str, str] = {}


def compute_icon_hash(name: str) -> str:
    """Return a short content hash (first 10 hex chars) of the icon file.

    Computes and caches the hash; invalidated automatically if file mtime changes.
    """
    path = get_icon_path(name)
    key = f"{name}:{path.stat().st_mtime_ns}"  # include mtime for invalidation
    cached = _hash_cache.get(key)
    if cached:
        return cached
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()[:10]
    # purge any prior entries for this name to prevent cache growth on edits
    for k in list(_hash_cache.keys()):
        if k.startswith(f"{name}:"):
            _hash_cache.pop(k)
    _hash_cache[key] = digest
    return digest


def get_icon_hash_map() -> Dict[str, str]:
    """Return mapping of icon name -> current content hash."""
    return {desc.name: compute_icon_hash(desc.name) for desc in list_icons()}


def export_icon_hash_map(path: Path) -> Dict[str, Dict[str, str]]:
    """Export a JSON file containing icon hash metadata.

    Format:
    {
       "icon-name": {"hash": "abc123...", "path": "assets/icons/base/icon-name.svg"}
    }
    Returns the structure written for further assertions.
    """
    mapping: Dict[str, Dict[str, str]] = {}
    for desc in list_icons():
        if desc.path.is_absolute():
            try:
                rel_path = desc.path.relative_to(Path.cwd())
            except ValueError:  # different drive or outside project root
                rel_path = desc.path
        else:
            rel_path = desc.path
        mapping[desc.name] = {
            "hash": compute_icon_hash(desc.name),
            "path": rel_path.as_posix(),
        }
    path.write_text(json.dumps(mapping, indent=2, sort_keys=True), encoding="utf-8")
    return mapping


# Pre-register core placeholder icon on import (safe if file missing? we enforce existence)
_placeholder = _BASE_ICON_DIR / "placeholder.svg"
if _placeholder.exists():  # guard for tests / partial clones
    try:
        register_icon("placeholder", _placeholder)
    except Exception:  # pragma: no cover - defensive; ignore duplicate when reloaded
        pass
