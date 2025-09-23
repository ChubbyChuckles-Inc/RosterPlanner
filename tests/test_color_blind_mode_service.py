from gui.services.color_blind_mode import ColorBlindModeService
from gui.services.service_locator import services


def test_color_blind_mode_set_and_callbacks():
    svc = ColorBlindModeService()
    history = []
    svc.on_change(lambda old, new: history.append((old, new)))
    assert svc.mode is None
    svc.set_mode("protanopia")
    assert svc.mode == "protanopia"
    svc.set_mode("deuteranopia")
    assert svc.mode == "deuteranopia"
    # Setting same mode again should not duplicate callback
    svc.set_mode("deuteranopia")
    assert history[0] == (None, "protanopia")
    assert history[1] == ("protanopia", "deuteranopia")
    assert len(history) == 2


def test_mainwindow_color_blind_menu_integration(qtbot):  # pragma: no cover - GUI interaction
    from gui.views.main_window import MainWindow

    # Ensure service registered
    services.register("color_blind_mode", ColorBlindModeService(), allow_override=True)
    win = MainWindow()
    qtbot.addWidget(win)  # type: ignore
    svc = services.get("color_blind_mode")
    assert svc.mode is None
    # Invoke the internal handler directly (simulating menu action)
    win._set_color_blind_mode("protanopia")
    assert svc.mode == "protanopia"
    win._set_color_blind_mode(None)
    assert svc.mode is None
