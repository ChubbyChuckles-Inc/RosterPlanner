import sys
import pytest

try:
    from PyQt6.QtWidgets import QApplication
except Exception:  # pragma: no cover
    QApplication = None  # type: ignore

from gui.views.main_window import MainWindow

CORE_DOCK_IDS = {"navigation", "availability", "detail", "stats", "planner", "logs", "database"}

_APP_HANDLE = None


def _ensure_app():
    global _APP_HANDLE
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    _APP_HANDLE = app
    return app


@pytest.mark.skipif(QApplication is None, reason="PyQt6 not available")
def test_core_docks_registered_and_created(qtbot, tmp_path):
    _ensure_app()
    _ = qtbot  # trigger fixture for symmetry with pytest-qt
    mw = MainWindow(club_id=1, season=2024, data_dir=str(tmp_path))
    try:
        qtbot.addWidget(mw)  # type: ignore[attr-defined]
    except Exception:
        pass
    # All IDs should be present
    ids = set(mw.dock_manager.list_ids())
    assert CORE_DOCK_IDS.issubset(ids)
    # Trigger creation for each (some already created initial two)
    for dock_id in CORE_DOCK_IDS:
        dock = mw.dock_manager.create(dock_id)
        assert dock is not None
        assert dock.objectName() == dock_id
    mw.close()
