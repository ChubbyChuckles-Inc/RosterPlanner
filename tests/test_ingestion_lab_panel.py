import os
import pytest

# Ensure Qt runs in offscreen/headless mode for tests if possible
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("RP_TEST_MODE", "1")

from PyQt6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


def test_ingestion_lab_panel_basic():
    from gui.views.ingestion_lab_panel import IngestionLabPanel

    panel = IngestionLabPanel(base_dir="data")
    # Should have at least file list and log area attributes
    assert hasattr(panel, "file_list"), "file_list missing"
    assert hasattr(panel, "log_area"), "log_area missing"
    # Trigger a refresh and ensure model row count is non-negative (sanity)
    panel.refresh_file_list()
    rows = panel.file_list.count()
    assert rows >= 0


def test_main_window_has_ingestion_lab_dock():
    from gui.views.main_window import MainWindow

    win = MainWindow()
    # Access dock manager registry to ensure ingestionlab factory present
    created = False
    dock = win.dock_manager.create("ingestionlab")
    assert dock is not None, "Ingestion Lab dock could not be created"
    # Basic smoke: widget inside dock should be IngestionLabPanel or placeholder
    inner = dock.widget()
    assert inner is not None
