"""GUI application entry point."""

from __future__ import annotations
import sys
from PyQt6.QtWidgets import QApplication
from gui.main_window import MainWindow
from config import settings


def main():  # pragma: no cover - GUI runtime
    app = QApplication(sys.argv)
    win = MainWindow(club_id=2294, season=2025, data_dir=settings.DATA_DIR)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":  # pragma: no cover
    main()
