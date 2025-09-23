from gui.services.service_locator import services
from gui.views.main_window import MainWindow
from gui.services.theme_service import ThemeService
from gui.services.event_bus import EventBus
import sys
from io import StringIO

# Headless safe: we won't actually show dialogs because we don't exec the event loop here.


def test_contrast_check_command_invokable(qtbot):
    # Register required services
    services.register("event_bus", EventBus(), allow_override=True)
    services.register("theme_service", ThemeService.create_default(), allow_override=True)
    win = MainWindow()
    qtbot.addWidget(win)  # type: ignore
    # Capture stdout to validate logging side-effect
    buf = StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        win._run_contrast_check(headless=True)
    finally:
        sys.stdout = old_stdout
    output = buf.getvalue()
    assert "[contrast-check] start" in output
    # Either success or at least one failure marker
    assert ("[contrast-success]" in output) or ("[contrast-failure]" in output)
