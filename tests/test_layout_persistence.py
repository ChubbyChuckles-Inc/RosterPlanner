import json
import os
import sys
import pytest

try:
    from PyQt6.QtWidgets import QApplication, QMainWindow
except Exception:  # pragma: no cover
    QApplication = None  # type: ignore

from gui.services.layout_persistence import LayoutPersistenceService, LAYOUT_VERSION


@pytest.mark.skipif(QApplication is None, reason="PyQt6 not available")
def test_layout_save_and_load(tmp_path):
    if QApplication.instance() is None:
        _app = QApplication(sys.argv)  # noqa: F841
    win = QMainWindow()
    svc = LayoutPersistenceService(str(tmp_path))
    assert svc.save_layout("main", win)
    # Modify file to ensure load returns True
    win2 = QMainWindow()
    assert svc.load_layout("main", win2)


@pytest.mark.skipif(QApplication is None, reason="PyQt6 not available")
def test_layout_version_mismatch(tmp_path):
    if QApplication.instance() is None:
        _app = QApplication(sys.argv)  # noqa: F841
    win = QMainWindow()
    svc = LayoutPersistenceService(str(tmp_path))
    svc.save_layout("profile", win)
    path = os.path.join(str(tmp_path), "layout_profile.json")
    # Corrupt / alter version
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["version"] = LAYOUT_VERSION + 1
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    win2 = QMainWindow()
    assert not svc.load_layout("profile", win2)
