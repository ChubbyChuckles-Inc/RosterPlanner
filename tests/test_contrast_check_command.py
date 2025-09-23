from gui.services.service_locator import services
from gui.views.main_window import MainWindow
from gui.services.theme_service import ThemeService
from gui.services.event_bus import EventBus

# Headless safe: we won't actually show dialogs because we don't exec the event loop here.


def test_contrast_check_command_invokable(qtbot):
    # Register required services
    services.register("event_bus", EventBus(), allow_override=True)
    services.register("theme_service", ThemeService.create_default(), allow_override=True)
    win = MainWindow()
    qtbot.addWidget(win)  # type: ignore
    # Simply invoke method; ensure it does not raise
    win._run_contrast_check()
