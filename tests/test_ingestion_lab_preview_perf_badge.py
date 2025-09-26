import os
from PyQt6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("RP_TEST_MODE", "1")
# Lower threshold so test triggers easily
os.environ["RP_ING_PREVIEW_PERF_THRESHOLD_MS"] = "5"

app = QApplication.instance() or QApplication([])

def test_preview_perf_badge_triggers(tmp_path, qtbot):
    from gui.views.ingestion_lab_panel import IngestionLabPanel

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    sample = data_dir / "sample.html"
    sample.write_text("<html><body>Alpha</body></html>", encoding="utf-8")

    panel = IngestionLabPanel(base_dir=str(data_dir))
    qtbot.addWidget(panel)
    panel.refresh_file_list()

    # Select first file
    first_child = None
    for r in range(panel.file_tree.topLevelItemCount()):
        phase_item = panel.file_tree.topLevelItem(r)
        if phase_item.childCount():
            first_child = phase_item.child(0)
            break
    assert first_child is not None
    panel.file_tree.setCurrentItem(first_child)

    # Directly exercise badge logic for deterministic timing independent of perf_counter
    panel._update_performance_badge(200.0)  # slow (> default 120ms threshold)
    assert getattr(panel, "_perf_badge_active", False) is True, "Performance badge state flag should be active for slow preview"
    assert "Preview" in panel._perf_badge.text()
    panel._update_performance_badge(1.0)  # fast
    assert getattr(panel, "_perf_badge_active", True) is False, "Performance badge state flag should be inactive for fast preview"