"""Application bootstrap utilities for the RosterPlanner GUI.

Responsibilities (Milestone 1.2 / 1.2.1):
 - High DPI attribute configuration (if PyQt6 available)
 - Optional headless bootstrap (for tests / environments without PyQt6)
 - Safe mode flag (disables future plugin loading & non-critical startup tasks)
 - Loading design tokens early and registering core services
 - Providing a single returned context object with references

The bootstrap deliberately avoids importing PyQt6 at module import time to keep
test collection fast and allow running unit tests in environments without a GUI.
"""

from __future__ import annotations

from dataclasses import dataclass
import sys
import time
from typing import Optional, Any

from gui.design import load_tokens, DesignTokens
from gui.i18n.direction import (
    set_layout_direction,
    apply_qt_direction,
    init_direction_from_env,
    get_layout_direction,
)
from gui.app.config_store import load_config, save_config, AppConfig
from gui.services.service_locator import services, ServiceLocator
from gui.services.event_bus import EventBus
from .timing import TimingLogger

try:  # Lazy / optional Qt import
    from PyQt6.QtCore import Qt  # type: ignore
    from PyQt6.QtWidgets import QApplication  # type: ignore

    _QT_AVAILABLE = True
except Exception:  # noqa: BLE001
    Qt = None  # type: ignore
    QApplication = None  # type: ignore
    _QT_AVAILABLE = False


@dataclass
class AppContext:
    """Container with references created during bootstrap.

    Attributes
    ----------
    qt_app: The underlying QApplication instance (None if headless or Qt missing)
    headless: Whether headless bootstrap was used
    safe_mode: Whether safe mode is active (plugins / extras skipped)
    design_tokens: Loaded design tokens
    services: Global service locator (post-initialization state)
    started_at: Monotonic timestamp when bootstrap started
    duration_s: Total elapsed seconds for bootstrap
    metadata: Free-form dict for future extensions
    """

    qt_app: Optional[Any]
    headless: bool
    safe_mode: bool
    design_tokens: DesignTokens
    services: ServiceLocator
    started_at: float
    duration_s: float
    metadata: dict[str, Any]
    timing: TimingLogger


def _configure_high_dpi() -> None:
    if not _QT_AVAILABLE:
        return
    # These attributes must be set before QApplication instantiation.
    # Guard for attribute existence to stay compatible with PyQt6 evolutions.
    if hasattr(Qt.ApplicationAttribute, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)


def parse_safe_mode(argv: list[str] | None = None) -> bool:
    """Parse a `--safe-mode` flag from argv (non-destructive)."""
    args = argv if argv is not None else sys.argv[1:]
    return "--safe-mode" in args


def parse_rtl(argv: list[str] | None = None) -> bool:
    """Parse a `--rtl` flag from argv.

    This flag forces RTL layout direction regardless of environment variable.
    """
    args = argv if argv is not None else sys.argv[1:]
    return "--rtl" in args


def create_app(
    *, safe_mode: bool | None = None, headless: bool | None = None, rtl: bool | None = None
) -> AppContext:
    """Create and initialize the GUI application context.

    Parameters
    ----------
    safe_mode: Explicit safe mode override. If None, inferred from argv.
    headless: Force headless (no QApplication). If None, inferred by Qt availability.
    """
    started = time.perf_counter()
    if safe_mode is None:
        safe_mode = parse_safe_mode()
    if rtl is None:
        rtl = parse_rtl()
    if headless is None:
        headless = not _QT_AVAILABLE

    timing = TimingLogger()

    qt_app = None
    if not headless and _QT_AVAILABLE:
        with timing.measure("qt_high_dpi_config"):
            _configure_high_dpi()
        with timing.measure("create_qapplication"):
            qt_app = QApplication.instance() or QApplication(sys.argv[:1])  # minimal argv
        # Determine initial direction: env variable first then CLI override
        with timing.measure("init_layout_direction"):
            init_direction_from_env()
            if rtl:
                set_layout_direction("rtl")
            # Apply to QApplication object
            apply_qt_direction(qt_app)

    # Core design tokens load early (may be needed by splash / theme system later)
    with timing.measure("load_design_tokens"):
        tokens = load_tokens()
    with timing.measure("load_app_config"):
        app_config = load_config()
    # Register services if not already present (idempotent behavior desired)
    # Use allow_override=False to avoid accidental replacement.
    with timing.measure("register_services"):
        try:
            services.register("design_tokens", tokens)
        except Exception:  # noqa: BLE001 - ignore double registration
            pass
        try:
            services.register("safe_mode", safe_mode)
        except Exception:  # noqa: BLE001
            pass
        # Always override previous startup timing (each bootstrap has its own session metrics)
        services.register("startup_timing", timing, allow_override=True)
        # Register EventBus if not already present
        # Always provide a fresh EventBus each bootstrap (test isolation)
        services.register("event_bus", EventBus(), allow_override=True)

    timing.stop()

    ctx = AppContext(
        qt_app=qt_app,
        headless=headless,
        safe_mode=safe_mode,
        design_tokens=tokens,
        services=services,
        started_at=started,
        duration_s=timing.total_duration,
        metadata={
            "qt_available": _QT_AVAILABLE,
            "startup_timing": timing.as_dict(),
            "app_config": app_config.to_dict(),
            "layout_direction": get_layout_direction(),
        },
        timing=timing,
    )
    return ctx


__all__ = ["AppContext", "create_app", "parse_safe_mode", "parse_rtl"]
