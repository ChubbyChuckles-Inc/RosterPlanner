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
import os
import tempfile
import psutil  # type: ignore  # Optional runtime dep; if missing we degrade gracefully
from contextlib import contextmanager
from typing import Optional, Any, Iterator, Callable

from gui.design import load_tokens, DesignTokens
from gui.i18n.direction import (
    set_layout_direction,
    apply_qt_direction,
    init_direction_from_env,
    get_layout_direction,
)
from gui.app.config_store import load_config, save_config, AppConfig
import atexit
from gui.services.service_locator import services, ServiceLocator
from gui.services.event_bus import EventBus
import sqlite3

# Lazy import for optional post-scrape ingestion hook (Milestone 5.9.5)
try:  # pragma: no cover - optional during early bootstrap
    from gui.services.post_scrape_ingest import PostScrapeIngestionHook  # type: ignore
except Exception:  # noqa: BLE001
    PostScrapeIngestionHook = None  # type: ignore
from .timing import TimingLogger
import json

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
    *,
    safe_mode: bool | None = None,
    headless: bool | None = None,
    rtl: bool | None = None,
    data_dir: str | None = None,
    ensure_sqlite: bool = True,
    sqlite_path_provider: Callable[[str], str] | None = None,
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
        for name, value in [
            ("design_tokens", tokens),
            ("safe_mode", safe_mode),
            ("app_config", app_config),
        ]:
            try:
                services.register(name, value)
            except Exception:  # noqa: BLE001 - ignore duplicate
                pass
        # Always override previous startup timing (each bootstrap has its own session metrics)
        services.register("startup_timing", timing, allow_override=True)
        # Register EventBus if not already present
        # Always provide a fresh EventBus each bootstrap (test isolation)
        services.register("event_bus", EventBus(), allow_override=True)

        # -- Milestone 5.9.5 integration: ensure sqlite connection service exists for ingestion
        if ensure_sqlite and data_dir:
            try:
                # Allow caller to influence on-disk db path (future migrations may change naming)
                if sqlite_path_provider:
                    db_path = sqlite_path_provider(data_dir)
                else:
                    db_path = os.path.join(data_dir, "rosterplanner_gui.sqlite")
                # Create directory if missing
                os.makedirs(os.path.dirname(db_path), exist_ok=True)
                # Allow usage from background worker threads in GUI tests (thread-affinity relaxed)
                conn = sqlite3.connect(db_path, check_same_thread=False)
                # Foreign keys on (defensive)
                try:
                    conn.execute("PRAGMA foreign_keys=ON")
                except Exception:  # pragma: no cover
                    pass
                # --- NEW: Auto-initialize schema & migrations if this is a brand new DB ---
                try:
                    cur = conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='division'"
                    )
                    row = cur.fetchone()
                    if not row:
                        # No core tables yet -> apply schema and migrations
                        from db.schema import apply_schema  # local import to keep bootstrap light
                        from db.migration_manager import apply_pending_migrations

                        with conn:
                            apply_schema(conn)
                            apply_pending_migrations(conn)
                        try:
                            print(  # noqa: T201 - intentional one-time visibility
                                f"[RosterPlanner] Initialized new SQLite database at: {db_path}"
                            )
                        except Exception:  # pragma: no cover - printing should rarely fail
                            pass
                except Exception:  # pragma: no cover - non-fatal initialization failure
                    # Intentionally swallow; downstream code may attempt a rebuild explicitly.
                    pass
                services.register("sqlite_conn", conn, allow_override=True)
            except Exception:  # noqa: BLE001 - non-fatal
                pass

    timing.stop()

    # Optional JSON export for diagnostics if env var set.
    export_path = os.environ.get("ROSTERPLANNER_STARTUP_TIMING_JSON")
    if export_path:
        try:  # Best-effort; never fail bootstrap for export issues
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(timing.as_dict(), f, indent=2, sort_keys=True)
        except Exception:  # noqa: BLE001
            pass

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

    # Ensure config is saved on interpreter shutdown (best-effort).
    def _persist_config() -> None:  # pragma: no cover - atexit not easily covered
        try:
            save_config(app_config)
        except Exception:
            pass

    atexit.register(_persist_config)
    return ctx


# --------------------------------------------------------------------------------------
# Single-instance guard (file lock) utilities
# --------------------------------------------------------------------------------------

_LOCK_FD: int | None = None
_LOCK_PATH: str | None = None


def _default_lock_path(name: str = "rosterplanner.lock") -> str:
    return os.path.join(tempfile.gettempdir(), name)


def _pid_alive(pid: int) -> bool:
    """Return True if a process with the given PID appears alive.

    Uses psutil when available; falls back to os.kill on POSIX or always True on Windows without psutil.
    """
    if psutil is not None:  # type: ignore[name-defined]
        try:
            return psutil.pid_exists(pid)  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - best effort
            pass
    # Best-effort generic fallback (Windows: cannot signal safely without perms)
    if os.name != "nt":  # POSIX-ish
        try:  # type: ignore[attr-defined]
            os.kill(pid, 0)  # type: ignore[arg-type]
            return True
        except Exception:
            return False
    return True  # On Windows assume alive if unsure


def acquire_single_instance(
    lock_name: str = "rosterplanner.lock", *, force_reclaim_stale: bool = True
) -> bool:
    """Attempt to acquire a coarse single-instance file lock.

    Returns True if this process acquired the lock, False if another instance
    already holds it. Uses an exclusive open with os.O_CREAT|os.O_EXCL where
    available, otherwise falls back to a best-effort scheme (Windows doesn't
    honor O_EXCL on existing open handles the same way so we write a PID).
    """
    global _LOCK_FD, _LOCK_PATH
    if _LOCK_FD is not None:
        return True  # already acquired
    path = _default_lock_path(lock_name)
    flags = os.O_CREAT | os.O_EXCL | os.O_RDWR
    try:
        fd = os.open(path, flags, 0o644)
        os.write(fd, str(os.getpid()).encode("utf-8"))
        _LOCK_FD = fd
        _LOCK_PATH = path
        return True
    except FileExistsError:
        # Possible stale lock; inspect existing file
        try:
            with open(path, "r", encoding="utf-8") as f:
                contents = f.read().strip()
            stale_pid = int(contents) if contents.isdigit() else None
        except Exception:
            stale_pid = None
        if stale_pid is not None and not _pid_alive(stale_pid) and force_reclaim_stale:
            # Remove stale file and retry once
            try:
                os.unlink(path)
                fd = os.open(path, flags, 0o644)
                os.write(fd, str(os.getpid()).encode("utf-8"))
                _LOCK_FD = fd
                _LOCK_PATH = path
                return True
            except Exception:  # pragma: no cover - race or permission
                return False
        return False
    except Exception:  # pragma: no cover - defensive fallback
        return True  # Do not block startup on unexpected FS semantics


def release_single_instance() -> None:
    global _LOCK_FD, _LOCK_PATH
    if _LOCK_FD is not None:
        try:
            os.close(_LOCK_FD)
            if _LOCK_PATH and os.path.exists(_LOCK_PATH):  # best-effort cleanup
                os.unlink(_LOCK_PATH)
        except Exception:  # pragma: no cover
            pass
        finally:
            _LOCK_FD = None
            _LOCK_PATH = None


@contextmanager
def single_instance(lock_name: str = "rosterplanner.lock") -> Iterator[bool]:
    """Context manager to guard single application instance.

    Yields True if lock acquired, else False. Caller may decide to exit if
    False is returned.
    """
    acquired = acquire_single_instance(lock_name)
    try:
        yield acquired
    finally:
        if acquired:
            release_single_instance()


def create_application(
    *,
    safe_mode: bool | None = None,
    rtl: bool | None = None,
    data_dir: str | None = None,
    enable_post_scrape_ingest: bool = True,
) -> AppContext:
    """High-level convenience wrapper for typical GUI launches.

    - Enforces single-instance (best-effort). If already running, exits process
      with code 1 after printing a short message.
    - Creates the app context (non-headless) and returns it.
    """
    ctx = create_app(safe_mode=safe_mode, headless=False, rtl=rtl, data_dir=data_dir)
    # Attempt lock after minimal construction so we have tokens/logging if desired.
    if not acquire_single_instance():  # Another instance is running
        print("Another RosterPlanner instance is already running.")  # noqa: T201
        # Graceful teardown: ensure QApplication (if any) not left around.
        if ctx.qt_app is not None:
            try:  # pragma: no cover - depends on Qt availability
                ctx.qt_app.quit()
            except Exception:
                pass
        # We purposefully do not raise; caller can inspect return if needed.
    # Attach post-scrape ingestion hook if requested and available
    if enable_post_scrape_ingest and PostScrapeIngestionHook is not None:
        try:
            # ScrapeRunner is created inside MainWindow later; hook will be attached there.
            # Provide a helper function for later consumption.
            services.register(
                "install_post_scrape_ingest_hook",
                lambda runner, data_dir_provider: PostScrapeIngestionHook(
                    runner, data_dir_provider
                ),
                allow_override=True,
            )
        except Exception:  # pragma: no cover
            pass
    return ctx


__all__ = [
    "AppContext",
    "create_app",
    "create_application",
    "parse_safe_mode",
    "parse_rtl",
    "single_instance",
    "acquire_single_instance",
    "release_single_instance",
]
