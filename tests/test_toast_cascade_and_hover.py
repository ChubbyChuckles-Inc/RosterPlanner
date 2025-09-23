import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from PyQt6.QtTest import QTest

from gui.components.toast_host import ToastHost, NotificationManager


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_cascade_stacking_order(qapp):
    host = ToastHost()
    mgr = NotificationManager(
        host, theme_service=None, disable_timers=True, enable_animations=False
    )
    ids = [
        mgr.show_notification("info", "Info 1"),
        mgr.show_notification("success", "Success 1"),
        mgr.show_notification("warning", "Warn"),
        mgr.show_notification("critical", "Crit"),
    ]
    widgets = host.toast_widgets()
    severities = [w.property("severity") for w in widgets]
    assert severities[0] in ("critical", "error"), severities
    for s in severities:
        assert s in ("info", "success", "warning", "critical"), s
    assert len(widgets) == len(ids)


def test_hover_pause_resume(qapp):
    host = ToastHost()
    mgr = NotificationManager(
        host, theme_service=None, disable_timers=False, enable_animations=False
    )
    notif_id = mgr.show_notification("info", "Will pause", timeout_override_ms=800)
    data = mgr._notifications[notif_id]
    assert data.timer is not None
    QTest.qWait(200)
    data.widget.enterEvent(None)  # type: ignore[arg-type]
    remaining_after_pause = data.remaining_ms
    assert data.paused is True and remaining_after_pause > 0
    QTest.qWait(300)
    assert notif_id in mgr._notifications
    data.widget.leaveEvent(None)  # type: ignore[arg-type]
    assert data.paused is False
    wait_time = max(remaining_after_pause + 120, 250)
    QTest.qWait(wait_time)
    QTimer.singleShot(0, lambda: None)
    QTest.qWait(10)
    assert notif_id not in mgr._notifications
