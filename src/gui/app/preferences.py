"""User preference persistence (Milestone 0.26).

Stores user-adjustable visual customization settings and related toggles
independent from transient window geometry (handled by config_store).

Design Goals
------------
- Pure-Python (no Qt import) to allow headless unit tests.
- Explicit schema with versioning for forward migrations.
- Graceful fallback on corrupt / incompatible data.
- Small surface: load_preferences / save_preferences + dataclass.

Future extensions (not yet implemented):
- Per-profile support (multiple named preference sets).
- Preference change notification (will integrate with EventBus later).
- Migration helpers across PREF_VERSION bumps.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from pathlib import Path
from typing import Any, Dict, Optional

__all__ = [
    "UserPreferences",
    "load_preferences",
    "save_preferences",
    "PREF_VERSION",
]

PREF_VERSION = 1
PREF_FILENAME = "user_prefs.json"


@dataclass
class UserPreferences:
    """Serializable user preference settings.

    Attributes
    ----------
    version: Schema version for future migrations.
    theme: Name of the currently selected theme (e.g. "light", "dark").
    accent: Optional accent color identifier (token key or hex) - validated elsewhere.
    density: Layout density mode ("comfortable" or "compact").
    high_contrast: Whether high contrast variant is enabled.
    reduce_motion: Whether to minimize animations / motion.
    locale: Preferred locale code (placeholder for future i18n integration).
    """

    version: int = PREF_VERSION
    theme: str = "light"
    accent: Optional[str] = None
    density: str = "comfortable"
    high_contrast: bool = False
    reduce_motion: bool = False
    locale: str = "en"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserPreferences":
        return cls(
            version=int(data.get("version", PREF_VERSION)),
            theme=str(data.get("theme", "light")),
            accent=data.get("accent"),
            density=str(data.get("density", "comfortable")),
            high_contrast=bool(data.get("high_contrast", False)),
            reduce_motion=bool(data.get("reduce_motion", False)),
            locale=str(data.get("locale", "en")),
        )


def _resolve_path(base_dir: str | Path | None) -> Path:
    base = Path(base_dir) if base_dir else Path.cwd()
    return base / PREF_FILENAME


def load_preferences(base_dir: str | Path | None = None) -> UserPreferences:
    path = _resolve_path(base_dir)
    if not path.exists():
        return UserPreferences()
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        prefs = UserPreferences.from_dict(data)
        if prefs.version != PREF_VERSION:
            # Preserve some fields if desired; for now full reset but keep theme if present.
            preserved_theme = prefs.theme if isinstance(prefs.theme, str) else "light"
            return UserPreferences(theme=preserved_theme)
        return prefs
    except Exception:  # noqa: BLE001
        return UserPreferences()


def save_preferences(prefs: UserPreferences, base_dir: str | Path | None = None) -> Path:
    path = _resolve_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(prefs.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    return path
