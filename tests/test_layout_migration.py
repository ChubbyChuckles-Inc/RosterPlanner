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
def test_layout_version_migration(tmp_path):
    if QApplication.instance() is None:
        _app = QApplication(sys.argv)  # noqa: F841
    svc = LayoutPersistenceService(str(tmp_path))
    win = QMainWindow()
    assert svc.save_layout("main", win)
    path = os.path.join(str(tmp_path), "layout_main.json")
    # Mutate version to simulate legacy file
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["version"] = LAYOUT_VERSION + 5
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    # Load should detect mismatch, back up file, and return False (no layout applied)
    win2 = QMainWindow()
    assert not svc.load_layout("main", win2)
    # Backup file should exist
    backups = [
        p
        for p in os.listdir(str(tmp_path))
        if p.startswith("layout_main.json.v") and p.endswith(".bak")
    ]
    assert backups, "Expected versioned backup file for migrated layout"
    # Original path should now be absent
    assert not os.path.exists(path)


@pytest.mark.skipif(QApplication is None, reason="PyQt6 not available")
def test_layout_corrupt_migration(tmp_path):
    if QApplication.instance() is None:
        _app = QApplication(sys.argv)  # noqa: F841
    svc = LayoutPersistenceService(str(tmp_path))
    win = QMainWindow()
    assert svc.save_layout("profile", win)
    path = os.path.join(str(tmp_path), "layout_profile.json")
    # Corrupt file with invalid JSON
    with open(path, "w", encoding="utf-8") as f:
        f.write("{not-json")
    win2 = QMainWindow()
    assert not svc.load_layout("profile", win2)
    # Corrupt backup should exist
    backups = [
        p
        for p in os.listdir(str(tmp_path))
        if p.startswith("layout_profile.json") and ".corrupt.bak" in p
    ]
    assert backups, "Expected corrupt backup file for invalid layout"
    assert not os.path.exists(path)
