"""Dedicated launcher module for `python -m gui` or external callers.

Now delegates to the unified bootstrap (`create_application`) so that all
first-run responsibilities (SQLite creation, schema + migrations, service
registration, single-instance guard, etc.) are exercised consistently.
"""

from __future__ import annotations

import sys
import os
from config import settings
from gui.main_window import MainWindow
from gui.app.bootstrap import create_application


def main():  # pragma: no cover - runtime
    # Use central bootstrap so auto schema initialization executes.
    ctx = create_application(data_dir=settings.DATA_DIR)
    app = ctx.qt_app  # created by bootstrap (non-headless)
    if app is None:  # Safety fallback (should not happen with PyQt available)
        from PyQt6.QtWidgets import QApplication  # type: ignore

        app = QApplication(sys.argv)
    # If single-instance not acquired, exit immediately (another instance shown message already)
    if ctx.metadata.get("single_instance_acquired") is False:  # type: ignore[truthy-bool]
        print("Another RosterPlanner instance is already running.")  # noqa: T201
        return 0
    # Allow forcing a clean geometry (skip persisted layout) if env var set
    if os.environ.get("ROSTERPLANNER_RESET_LAYOUT"):
        try:
            # Remove layout file proactively before window creation
            import os as _os

            layout_file = _os.path.join(settings.DATA_DIR, "layout_main.json")
            if _os.path.exists(layout_file):
                _os.remove(layout_file)
                print(f"[Launcher] Removed persisted layout: {layout_file}")  # noqa: T201
        except Exception:
            pass
    print("[Launcher] Creating MainWindow...", flush=True)  # noqa: T201
    win = MainWindow(club_id=2294, season=2025, data_dir=settings.DATA_DIR)
    print("[Launcher] Showing MainWindow", flush=True)  # noqa: T201
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":  # pragma: no cover
    main()
