"""Application layer for GUI bootstrap and lifecycle management.

Public exports include application bootstrap, context objects, and persistence
helpers (config & user preferences) for higher-level modules.
"""

from .bootstrap import create_app, AppContext, parse_safe_mode  # noqa: F401
from .config_store import (  # noqa: F401
    AppConfig,
    load_config,
    save_config,
    CONFIG_VERSION,
    WINDOW_STATE_VERSION,
)
from .preferences import (  # noqa: F401
    UserPreferences,
    load_preferences,
    save_preferences,
    PREF_VERSION,
)

__all__ = [
    "create_app",
    "AppContext",
    "parse_safe_mode",
    # Config store
    "AppConfig",
    "load_config",
    "save_config",
    "CONFIG_VERSION",
    "WINDOW_STATE_VERSION",
    # User preferences
    "UserPreferences",
    "load_preferences",
    "save_preferences",
    "PREF_VERSION",
]
