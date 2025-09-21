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
from .micro_interactions import (  # noqa: F401
    list_micro_interactions,
    get_micro_interaction,
    MicroInteraction,
)
from .performance_budgets import (  # noqa: F401
    list_performance_budgets,
    get_performance_budget,
    PerformanceBudget,
    enforce_budget,
)
from .skeletons import (  # noqa: F401
    list_skeleton_variants,
    get_skeleton_variant,
    SkeletonVariant,
)
from .empty_states import (  # noqa: F401
    list_empty_states,
    get_empty_state,
    EmptyStateTemplate,
)
from .error_states import (  # noqa: F401
    list_error_states,
    get_error_state,
    ErrorState,
)
from .notifications import (  # noqa: F401
    list_notification_styles,
    get_notification_style,
    NotificationStyle,
)

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
    "list_micro_interactions",
    "get_micro_interaction",
    "MicroInteraction",
    "list_performance_budgets",
    "get_performance_budget",
    "PerformanceBudget",
    "enforce_budget",
    "list_skeleton_variants",
    "get_skeleton_variant",
    "SkeletonVariant",
    "list_empty_states",
    "get_empty_state",
    "EmptyStateTemplate",
    "list_error_states",
    "get_error_state",
    "ErrorState",
    "list_notification_styles",
    "get_notification_style",
    "NotificationStyle",
]
