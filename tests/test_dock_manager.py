import os
import sys
import types

import pytest

# PyQt6 may not be available in some CI environments; skip if missing
try:
    from PyQt6.QtWidgets import QApplication
except Exception:  # pragma: no cover
    QApplication = None  # type: ignore

from gui.views.dock_manager import DockManager


def test_dock_manager_registration_and_creation():
    # Ensure a QApplication for QDockWidget usage
    try:
        if QApplication is not None and QApplication.instance() is None:
            import sys as _sys

            QApplication(_sys.argv[:1])  # type: ignore
    except Exception:
        pass
    dm = DockManager()
    created = []

    class _DummyWidget:
        pass

    def factory():
        w = _DummyWidget()
        created.append(w)
        return w  # type: ignore

    dm.register("a", "A", factory)
    dm.register("b", "B", factory)
    assert dm.is_registered("a") and dm.is_registered("b")
    assert dm.list_ids() == ["a", "b"]
    # create does not require real Qt widget in this fallback context if Qt absent
    inst_a = dm.create("a")
    inst_b = dm.create("b")
    assert inst_a is dm.get("a")
    assert inst_b is dm.get("b")
    assert len(created) == 2


@pytest.mark.skipif(QApplication is None, reason="PyQt6 not available")
def test_main_window_docks(qtbot, tmp_path):  # qtbot provided by pytest-qt if installed
    # If pytest-qt isn't installed, we can still instantiate a QApplication manually.
    if QApplication.instance() is None:
        _app = QApplication(sys.argv)  # noqa: F841
    from gui.views.main_window import MainWindow

    mw = MainWindow(club_id=1, season=2024, data_dir=str(tmp_path))
    # Ensure expected docks exist
    dock_ids = mw.dock_manager.list_ids()
    assert "navigation" in dock_ids
    assert "availability" in dock_ids
    # Docks should have been created & added
    assert mw.dock_manager.get("navigation") is not None
    assert mw.dock_manager.get("availability") is not None
