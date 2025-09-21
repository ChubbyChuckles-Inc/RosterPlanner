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
from .responsive import (  # noqa: F401
    list_breakpoints,
    get_breakpoint,
    classify_width,
    Breakpoint,
)
from .reflow import (  # noqa: F401
    list_reflow_rules,
    get_reflow_actions,
    ReflowRule,
)
from .interaction_latency import (  # noqa: F401
    instrument_latency,
    latency_block,
    get_latency_records,
    clear_latency_records,
    list_thresholds,
    register_threshold,
    LatencyRecord,
    LatencyThreshold,
)
from .color_drift import (  # noqa: F401
    scan_for_color_drift,
    normalize_hex,
    ColorDriftIssue,
)
from .inline_style_lint import (  # noqa: F401
    scan_for_inline_styles,
    InlineStyleIssue,
)
from .plugin_style_contract import (  # noqa: F401
    validate_style_mapping,
    scan_plugin_style_files,
    PluginStyleIssue,
)
from .print_stylesheet import (  # noqa: F401
    build_print_stylesheet,
    PrintStylesheetMeta,
)
from .snapshot_pipeline import (  # noqa: F401
    compute_image_hash,
    capture_bytes_placeholder,
    SnapshotRecord,
)
from .onboarding_tour import (  # noqa: F401
    register_tour,
    get_tour,
    list_tours,
    clear_tours,
    TourDefinition,
    TourStep,
)
from .focus_ring import (  # noqa: F401
    build_focus_ring_style,
    FocusRingStyle,
    contrast_ratio,
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
    "list_breakpoints",
    "get_breakpoint",
    "classify_width",
    "Breakpoint",
    "list_reflow_rules",
    "get_reflow_actions",
    "ReflowRule",
    "instrument_latency",
    "latency_block",
    "get_latency_records",
    "clear_latency_records",
    "list_thresholds",
    "register_threshold",
    "LatencyRecord",
    "LatencyThreshold",
    "scan_for_color_drift",
    "normalize_hex",
    "ColorDriftIssue",
    "scan_for_inline_styles",
    "InlineStyleIssue",
    "validate_style_mapping",
    "scan_plugin_style_files",
    "PluginStyleIssue",
    "build_print_stylesheet",
    "PrintStylesheetMeta",
    "compute_image_hash",
    "capture_bytes_placeholder",
    "SnapshotRecord",
    "register_tour",
    "get_tour",
    "list_tours",
    "clear_tours",
    "TourDefinition",
    "TourStep",
    "build_focus_ring_style",
    "FocusRingStyle",
    "contrast_ratio",
]
