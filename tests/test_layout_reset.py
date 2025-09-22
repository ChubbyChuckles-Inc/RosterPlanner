import os
import sys
import pytest

try:
    from PyQt6.QtWidgets import QApplication, QMainWindow
except Exception:  # pragma: no cover
    QApplication = None  # type: ignore

from gui.services.layout_persistence import LayoutPersistenceService


@pytest.mark.skipif(QApplication is None, reason="PyQt6 not available")
def test_layout_reset(tmp_path):
    if QApplication.instance() is None:
        _app = QApplication(sys.argv)  # noqa: F841
    svc = LayoutPersistenceService(str(tmp_path))
    win = QMainWindow()
    assert svc.save_layout("main", win)
    path = os.path.join(str(tmp_path), "layout_main.json")
    assert os.path.exists(path)
    assert svc.reset_layout("main")
    assert not os.path.exists(path)
    # Reset again returns False
    assert svc.reset_layout("main") is False
