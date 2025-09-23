from gui.components.skeleton_loader import SkeletonLoaderWidget
from gui.design.reduced_motion import set_reduced_motion, temporarily_reduced_motion
from PyQt6.QtWidgets import QApplication
import sys


def test_skeleton_shimmer_reduced_motion_disabled(qtbot):
    app = QApplication.instance() or QApplication(sys.argv)
    # Force reduced motion
    set_reduced_motion(True)
    w = SkeletonLoaderWidget("table-row", rows=1, shimmer=True, shimmer_interval_ms=80)
    qtbot.addWidget(w)
    w.start()
    # Shimmer should be disabled
    assert not w.shimmer_enabled()
    assert w._shimmer_timer is None
    # Cleanup
    set_reduced_motion(False)
