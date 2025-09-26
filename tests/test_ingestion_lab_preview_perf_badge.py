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
    assert (
        getattr(panel, "_perf_badge_active", False) is True
    ), "Performance badge state flag should be active for slow preview"
    assert "Preview" in panel._perf_badge.text()
    panel._update_performance_badge(1.0)  # fast
    assert (
        getattr(panel, "_perf_badge_active", True) is False
    ), "Performance badge state flag should be inactive for fast preview"


# Add tests for batch preview skeleton (Milestone 7.10.46)


def test_batch_preview_skeleton_shows_and_hides(qtbot, tmp_path, monkeypatch):
    from gui.views.ingestion_lab_panel import IngestionLabPanel

    # Create temporary HTML files
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    file_paths = []
    for i in range(6):  # >= default threshold 5
        p = data_dir / f"sample_{i}.html"
        p.write_text(f"<html><body><div>File {i}</div></body></html>")
        file_paths.append(str(p))
    panel = IngestionLabPanel(str(data_dir))
    qtbot.addWidget(panel)
    panel.refresh_file_list()

    # Select multiple child items
    items = []
    top_count = panel.file_tree.topLevelItemCount()
    for r in range(top_count):
        top = panel.file_tree.topLevelItem(r)
        for c in range(top.childCount()):
            items.append(top.child(c))
    # Ensure we have enough
    assert len(items) >= 6
    panel.file_tree.clearSelection()
    for it in items[:6]:
        it.setSelected(True)
    # Force artificial delay small for deterministic skeleton show
    panel.batch_preview_artificial_delay_ms = 10
    panel._on_preview_clicked()
    # Skeleton should have been shown at some point
    assert panel._batch_skeleton_last_shown is True
    # After completion stack index should return to preview (0)
    assert panel._preview_stack.currentIndex() == 0
    txt = panel.preview_area.toPlainText()
    assert "Batch Preview" in txt and "6 files" in txt


def test_single_preview_unchanged_path(qtbot, tmp_path):
    from gui.views.ingestion_lab_panel import IngestionLabPanel

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    f = data_dir / "one.html"
    f.write_text("<html><body><p>Only</p></body></html>")
    panel = IngestionLabPanel(str(data_dir))
    qtbot.addWidget(panel)
    panel.refresh_file_list()
    # Select first child
    for r in range(panel.file_tree.topLevelItemCount()):
        top = panel.file_tree.topLevelItem(r)
        if top.childCount():
            child = top.child(0)
            child.setSelected(True)
            break
    panel._on_preview_clicked()
    assert "File:" in panel.preview_area.toPlainText()
    # Skeleton flag should remain False
    assert panel._batch_skeleton_last_shown is False
