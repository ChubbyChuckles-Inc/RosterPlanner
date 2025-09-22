"""Dedicated launcher module for `python -m gui` or external callers.

Now delegates to the unified bootstrap (`create_application`) so that all
first-run responsibilities (SQLite creation, schema + migrations, service
registration, single-instance guard, etc.) are exercised consistently.
"""

from __future__ import annotations

import sys
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
    win = MainWindow(club_id=2294, season=2025, data_dir=settings.DATA_DIR)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":  # pragma: no cover
    main()
