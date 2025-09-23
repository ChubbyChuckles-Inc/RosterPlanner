import os
import sys
from PyQt6.QtWidgets import QApplication


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication(sys.argv)


def test_toast_stacking_and_dismissal():
    _app()
    from gui.components.toast_host import ToastHost, NotificationManager
    from gui.services.theme_service import ThemeService

    host = ToastHost()
    theme = ThemeService.create_default()
    manager = NotificationManager(host, theme_service=theme, disable_timers=True)
    # Add info (priority 50) then warning (priority 30 => should stack before info)
    info_id = manager.show_notification("info", "Informational message")
    warn_id = manager.show_notification("warning", "Warning message")
    # Ensure both active
    ids = manager.active_ids()
    assert info_id in ids and warn_id in ids
    # Stacking: first widget (index 0) should be warning (lower stacking_priority)
    first_widget = host.layout().itemAt(0).widget()
    assert first_widget.property("style_id") == "warning"
    # Dismiss warning, ensure only info remains
    assert manager.dismiss(warn_id)
    remaining = manager.active_ids()
    assert remaining == [info_id]
    # Dismiss info
    assert manager.dismiss(info_id)
    assert manager.active_ids() == []
