from gui.components.skeleton_loader import SkeletonLoaderWidget
from PyQt6.QtWidgets import QApplication
import sys


def test_skeleton_shimmer_initial_state(qtbot):
    # Ensure QApplication exists (qtbot fallback may not construct early enough)
    app = QApplication.instance() or QApplication(sys.argv)
    w = SkeletonLoaderWidget("table-row", rows=1, shimmer=True, shimmer_interval_ms=120)
    qtbot.addWidget(w)
    w.start()
    assert w.is_active()
    assert w._shimmer_timer is not None
    # Simulate two shimmer ticks
    w._on_shimmer_tick()
    first = w.property("shimmerPhase")
    w._on_shimmer_tick()
    second = w.property("shimmerPhase")
    assert first != second
    w.stop()
    assert not w.is_active()
    assert w._shimmer_timer is None
