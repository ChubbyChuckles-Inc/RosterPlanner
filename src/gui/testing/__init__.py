"""Testing utilities for GUI-related (but headless-safe) verification.

This subpackage intentionally avoids importing PyQt at module import time to
keep tests fast and headless-friendly. Utilities that need PyQt must import
it lazily inside functions.
"""

from __future__ import annotations

__all__ = [
    "capture_widget_screenshot",
    "hash_image_bytes",
    "compare_or_update_baseline",
    "VisualDiffResult",
    "compute_logical_focus_order",
    "focus_order_names",
    "tab_traversal_widgets",
    "tab_traversal_names",
]

from .visual_regression import (
    capture_widget_screenshot,
    hash_image_bytes,
    compare_or_update_baseline,
    VisualDiffResult,
)
from .focus import (
    compute_logical_focus_order,
    focus_order_names,
    tab_traversal_widgets,
    tab_traversal_names,
)
