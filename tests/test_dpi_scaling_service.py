from __future__ import annotations

import math

from PyQt6.QtWidgets import QApplication

from gui.services.dpi_scaling_service import DpiScalingService
from gui.services.event_bus import EventBus, GUIEvent
from gui.services.service_locator import services


def test_dpi_scaling_emits_on_threshold(tmp_path):
    # Ensure QApplication
    app = QApplication.instance() or QApplication([])
    services.register("event_bus", EventBus(), allow_override=True)
    scales = [1.0, 1.005, 1.012, 1.012, 1.25]
    index = {"i": 0}

    def _fake_scale():
        return scales[index["i"]]

    svc = DpiScalingService(get_scale=_fake_scale)
    events: list[float] = []

    def _handler(evt):
        events.append(evt.payload["scale"])  # type: ignore

    bus = services.get_typed("event_bus", EventBus)
    bus.subscribe(GUIEvent.DPI_SCALE_CHANGED, _handler)

    # Simulate changes
    for i in range(1, len(scales)):
        index["i"] = i
        svc._emit_if_changed()  # directly invoke internal (deterministic)

    # Should skip 1.005 (<1%), emit for 1.012, skip duplicate 1.012, emit for 1.25
    assert len(events) == 2
    assert math.isclose(events[0], 1.012, rel_tol=1e-6)
    assert math.isclose(events[1], 1.25, rel_tol=1e-6)
