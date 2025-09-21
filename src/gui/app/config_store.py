"""Application configuration persistence (Milestone 1.3).

Stores and loads lightweight UI/runtime state such as window geometry and last
used data directory. Designed for testability and forward compatibility.

Design principles:
- Pure logic (no direct Qt import) so it can be unit-tested headless.
- Explicit schema with version field to enable future migrations.
- Graceful fallback: corrupt or incompatible files produce defaults instead of raising.
- Small surface: load_config / save_config plus dataclass.

Future extensions (not implemented yet):
- Per-user OS-specific config directory resolution.
- Encryption for sensitive fields (not currently needed).
- Incremental migration helpers when version increases.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from pathlib import Path
from typing import Any, Dict, Optional

__all__ = ["AppConfig", "load_config", "save_config", "CONFIG_VERSION"]

CONFIG_VERSION = 1  # Increment when structure changes

DEFAULT_FILENAME = "app_state.json"


@dataclass(slots=True)
class AppConfig:
    """Serializable application state configuration.

    Attributes
    ----------
    version: Schema version for migration handling.
    window_x, window_y: Last top-left window coordinates (int or None if unknown).
    window_w, window_h: Last window size dimensions.
    maximized: Whether window was maximized at shutdown.
    last_data_dir: Recently used data directory (string path) or None.
    """

    version: int = CONFIG_VERSION
    window_x: Optional[int] = None
    window_y: Optional[int] = None
    window_w: Optional[int] = None
    window_h: Optional[int] = None
    maximized: bool = False
    last_data_dir: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        # Basic defensive parsing
        return cls(
            version=int(data.get("version", CONFIG_VERSION)),
            window_x=data.get("window_x"),
            window_y=data.get("window_y"),
            window_w=data.get("window_w"),
            window_h=data.get("window_h"),
            maximized=bool(data.get("maximized", False)),
            last_data_dir=data.get("last_data_dir"),
        )

    def is_geometry_complete(self) -> bool:
        return (
            self.window_x is not None
            and self.window_y is not None
            and self.window_w is not None
            and self.window_h is not None
        )


def _resolve_path(base_dir: str | Path | None) -> Path:
    base = Path(base_dir) if base_dir else Path.cwd()
    return base / DEFAULT_FILENAME


def load_config(base_dir: str | Path | None = None) -> AppConfig:
    """Load application config from directory.

    Parameters
    ----------
    base_dir: The directory containing the config file (defaults to CWD).
    """
    path = _resolve_path(base_dir)
    if not path.exists():
        return AppConfig()
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        cfg = AppConfig.from_dict(data)
        if cfg.version != CONFIG_VERSION:
            # For now just reset to defaults while preserving last_data_dir if possible.
            preserved_last = cfg.last_data_dir
            return AppConfig(last_data_dir=preserved_last)
        return cfg
    except Exception:  # noqa: BLE001
        return AppConfig()


def save_config(cfg: AppConfig, base_dir: str | Path | None = None) -> Path:
    """Persist application config to directory.

    Returns the path written for convenience.
    """
    path = _resolve_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(cfg.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    return path
