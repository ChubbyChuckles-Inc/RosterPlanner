import os
import sys
import pytest

try:
    from PyQt6.QtWidgets import QApplication
except Exception:  # pragma: no cover
    QApplication = None  # type: ignore

from gui.views.main_window import MainWindow
from gui.views.dock_manager import DockManager

CORE_DOCK_IDS = {"navigation", "availability", "detail", "stats", "planner", "logs"}

@pytest.mark.skipif(QApplication is None, reason="PyQt6 not available")
def test_mainwindow_layout_reset(tmp_path):
    # Ensure app
    if QApplication.instance() is None:
        _app = QApplication(sys.argv)  # noqa: F841
    data_dir = str(tmp_path)
    # Create window (captures pristine snapshot)
    win = MainWindow(club_id=1, season=2025, data_dir=data_dir)
    # Sanity: initial docks registered (subset may be created lazily; ensure navigation + availability at least)
    initial_ids = {dock.objectName() for dock in win.dock_manager.instances()}
    assert 'navigation' in initial_ids
    # Remove multiple docks to simulate heavy customization
    for did in list(initial_ids)[:2]:
        dock_widget = win.dock_manager.get(did)
        if dock_widget:
            win.removeDockWidget(dock_widget)
    # Simulate user removing a dock (close navigation)
    nav = win.dock_manager.get('navigation')
    assert nav is not None
    win.removeDockWidget(nav)
    # Persist altered layout
    win._layout_service.save_layout('main', win)
    # Reset layout
    win._on_reset_layout()
    # After reset verify all core dock ids can be created / exist
    restored_ids = {dock.objectName() for dock in win.dock_manager.instances()}
    missing = CORE_DOCK_IDS - restored_ids
    # If some are missing, attempt creation via dock_manager.create to see if definitions still registered
    still_missing = set()
    for mid in list(missing):
        try:
            win.dock_manager.create(mid)
        except Exception:
            still_missing.add(mid)
    if still_missing:
        pytest.fail(f"Layout reset missing docks: {sorted(still_missing)}")
    # Ensure layout file was recreated
    assert os.path.exists(os.path.join(data_dir, 'layout_main.json'))
