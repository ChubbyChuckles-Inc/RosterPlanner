import os
import sys
from PyQt6.QtWidgets import QApplication


def test_skeleton_loader_basic():
    # Ensure headless friendly
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication(sys.argv)
    from gui.components.skeleton_loader import SkeletonLoaderWidget

    skel = SkeletonLoaderWidget("table-row", rows=2)
    assert skel.variant_name() == "table-row"
    skel.start()
    assert skel.is_active()
    skel.stop()
    assert not skel.is_active()
    # keep reference to prevent premature GC
    app.processEvents()
