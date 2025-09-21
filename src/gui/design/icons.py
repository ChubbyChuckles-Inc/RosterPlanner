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
from pathlib import Path
from threading import RLock
from typing import Dict, Iterable, Optional

__all__ = [
    "IconDescriptor",
    "register_icon",
    "get_icon_path",
    "list_icons",
    "clear_icons",
]

# Base directory for built-in icons (relative to project root). Adjust if packaging changes.
_BASE_ICON_DIR = Path(__file__).resolve().parents[3] / "assets" / "icons" / "base"

_lock = RLock()
_registry: Dict[str, "IconDescriptor"] = {}


@dataclass(slots=True)
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


# Pre-register core placeholder icon on import (safe if file missing? we enforce existence)
_placeholder = _BASE_ICON_DIR / "placeholder.svg"
if _placeholder.exists():  # guard for tests / partial clones
    try:
        register_icon("placeholder", _placeholder)
    except Exception:  # pragma: no cover - defensive; ignore duplicate when reloaded
        pass
