"""GUI application entry point."""

from __future__ import annotations
import sys
from PyQt6.QtWidgets import QApplication
from gui.services.service_locator import services
from gui.services.event_bus import EventBus
from gui.services.dpi_scaling_service import install_dpi_scaling_service
from gui.main_window import MainWindow
from config import settings


def main():  # pragma: no cover - GUI runtime
    app = QApplication(sys.argv)
    # Minimal early service bootstrap (event bus + dpi scaling)
    try:
        if not services.try_get("event_bus"):
            services.register("event_bus", EventBus())
    except Exception:
        pass
    try:
        install_dpi_scaling_service()
    except Exception:
        pass
    win = MainWindow(club_id=2294, season=2025, data_dir=settings.DATA_DIR)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":  # pragma: no cover
    main()
