"""Design system package.

Contains design tokens, loaders, QSS generator utilities, and future theming extensions.
"""

from .loader import load_tokens, DesignTokens, TokenValidationError  # noqa: F401
from .icons import register_icon, get_icon_path, list_icons, clear_icons  # noqa: F401
from .motion import get_duration_ms, get_easing_curve, parse_cubic_bezier  # noqa: F401
from .theme_manager import ThemeManager, ThemeDiff  # noqa: F401
from .dynamic_accent import derive_accent_palette  # noqa: F401
from .density_manager import DensityManager, DensityDiff  # noqa: F401
from .qss_overrides import (
    sanitize_custom_qss,
    sanitize_custom_qss_detailed,
    apply_user_overrides,
    QSSValidationError,
    SanitizeResult,
)  # noqa: F401
from .color_blind import simulate_color_blindness, simulate_rgb_buffer  # noqa: F401
from .chart_palette import build_chart_palette, ChartPalette  # noqa: F401

__all__ = [
    "load_tokens",
    "DesignTokens",
    "TokenValidationError",
    "register_icon",
    "get_icon_path",
    "list_icons",
    "clear_icons",
    "get_duration_ms",
    "get_easing_curve",
    "parse_cubic_bezier",
    "ThemeManager",
    "ThemeDiff",
    "derive_accent_palette",
    "DensityManager",
    "DensityDiff",
    "sanitize_custom_qss",
    "sanitize_custom_qss_detailed",
    "apply_user_overrides",
    "SanitizeResult",
    "QSSValidationError",
    "simulate_color_blindness",
    "simulate_rgb_buffer",
    "build_chart_palette",
    "ChartPalette",
]
