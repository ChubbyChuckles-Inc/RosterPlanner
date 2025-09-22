import sys
import pytest

try:
    from PyQt6.QtWidgets import QApplication
except Exception:  # pragma: no cover
    QApplication = None  # type: ignore

from gui.views.main_window import MainWindow

CORE_DOCK_IDS = {"navigation", "availability", "detail", "stats", "planner", "logs"}


@pytest.mark.skipif(QApplication is None, reason="PyQt6 not available")
def test_core_docks_registered_and_created(tmp_path):
    if QApplication.instance() is None:
        _app = QApplication(sys.argv)  # noqa: F841
    mw = MainWindow(club_id=1, season=2024, data_dir=str(tmp_path))
    # All IDs should be present
    ids = set(mw.dock_manager.list_ids())
    assert CORE_DOCK_IDS.issubset(ids)
    # Trigger creation for each (some already created initial two)
    for dock_id in CORE_DOCK_IDS:
        dock = mw.dock_manager.create(dock_id)
        assert dock is not None
        assert dock.objectName() == dock_id
