import sys
from io import StringIO
import pytest

from gui.utils.theme_style_perf import apply_theme_qss


class _Host:
    def __init__(self):
        self._sheet = "QWidget {}"  # existing sheet

    def styleSheet(self):  # noqa: D401
        return self._sheet

    def setStyleSheet(self, qss: str):  # noqa: D401
        self._sheet = qss


class _EBus:
    def __init__(self):
        self.events = []

    def publish(self, name, payload):  # noqa: D401
        self.events.append((name, payload))


def test_theme_style_apply_instrumentation():
    host = _Host()
    bus = _EBus()
    big_block = "/* THEME (auto-generated runtime) */\n" + "\n".join(
        [f"QLabel {{ color: #123456; /* {i} */ }}" for i in range(300)]
    )
    buf = StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        duration, warned = apply_theme_qss(host, big_block, event_bus=bus, threshold_ms=0.0001)
    finally:
        sys.stdout = old
    out = buf.getvalue()
    assert "[theme-style-apply]" in out
    # For forced low threshold we expect warning path
    assert warned is True
    assert any(e[0] == "THEME_STYLE_APPLY_SLOW" for e in bus.events)
