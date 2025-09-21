"""Compatibility shim for legacy import path.

The dock-based implementation now lives in ``gui.views.main_window``.
Importing ``gui.main_window.MainWindow`` will continue to work but should
be updated to the new path in future refactors.
"""

from __future__ import annotations

from gui.views.main_window import MainWindow  # re-export

__all__ = ["MainWindow"]
