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
    # Count total file entries (children of phase nodes)
    total_files = 0
    for r in range(panel.file_tree.topLevelItemCount()):  # type: ignore[attr-defined]
        total_files += panel.file_tree.topLevelItem(r).childCount()  # type: ignore[attr-defined]
    assert total_files >= 0
    # Grouping accessors should function
    phases = panel.phases()
    assert isinstance(phases, list)
    listed = panel.listed_files()
    assert isinstance(listed, list)


def test_ingestion_lab_panel_provenance_columns():
    """If provenance table exists, panel should populate hash / last ingested columns.

    Test creates a temporary provenance row for one discovered file (if any) by
    mocking a minimal in-memory sqlite connection registered under service locator.
    Falls back to skip if no files present in data dir.
    """
    from gui.views.ingestion_lab_panel import IngestionLabPanel
    from gui.services.service_locator import services
    import sqlite3
    import glob

    pattern = os.path.join("data", "**", "*.html")
    files = glob.glob(pattern, recursive=True)
    if not files:
        pytest.skip("No HTML files available to test provenance display")
    sample = files[0]
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE provenance(path TEXT PRIMARY KEY, sha1 TEXT, last_ingested_at TEXT, parser_version INTEGER)"
    )
    conn.execute(
        "INSERT INTO provenance(path, sha1, last_ingested_at, parser_version) VALUES(?,?,datetime('now'),?)",
        (sample, "deadbeefcafebabe", 2),
    )
    # Use override_context so global sqlite_conn service is restored after test
    with services.override_context(sqlite_conn=conn):
        panel = IngestionLabPanel(base_dir="data")
        # Find the tree item matching the sample file and assert hash column populated
        found = False
        for r in range(panel.file_tree.topLevelItemCount()):  # type: ignore[attr-defined]
            phase_item = panel.file_tree.topLevelItem(r)  # type: ignore[attr-defined]
            for c in range(phase_item.childCount()):
                child = phase_item.child(c)
                if child.text(1) and child.text(1).endswith(os.path.basename(sample)):
                    # Hash column index 3 should have short hash prefix
                    hash_col = child.text(3)
                    assert (
                        hash_col.startswith("deadbeef"[: len(hash_col)])
                        or hash_col == "deadbeefcaf"[: len(hash_col)]
                    )
                    found = True
                    # Trigger preview to ensure provenance metadata surfaces
                    panel.file_tree.setCurrentItem(child)  # select
                    panel._on_preview_clicked()  # directly invoke
                    preview = panel.preview_area.toPlainText()
                    assert "deadbeefcafe"[:6] in preview or "deadbeef" in preview
                    assert "Parser Version" in preview
                    break
            if found:
                break
        assert found, "Expected provenance-enriched file row not found"


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


def test_ingestion_lab_panel_search_and_phase_filter(tmp_path, qtbot):
    from gui.views.ingestion_lab_panel import IngestionLabPanel, PHASE_PATTERNS

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    # Create representative files for different phases
    (data_dir / "ranking_table_alpha.html").write_text("<html>alpha</html>")
    (data_dir / "team_roster_beta.html").write_text("<html>beta</html>")
    (data_dir / "misc_gamma.html").write_text("<html>gamma</html>")

    panel = IngestionLabPanel(base_dir=str(data_dir))
    qtbot.addWidget(panel)
    panel.refresh_file_list()
    assert panel.filtered_file_count() == 3

    # Search filter (substring)
    panel.search_box.setText("alpha")
    panel._apply_filters()
    assert panel.filtered_file_count() == 1
    panel.search_box.clear()
    panel._apply_filters()
    assert panel.filtered_file_count() == 3

    # Phase filter: disable ranking tables phase
    ranking_phase_id = None
    for pid, label, _ in PHASE_PATTERNS:
        if "Ranking" in label:
            ranking_phase_id = pid
            break
    assert ranking_phase_id is not None
    cb = panel._phase_checks[ranking_phase_id]
    cb.setChecked(False)
    panel._apply_filters()
    assert panel.filtered_file_count() == 2


def test_ingestion_lab_panel_theme_density_integration(qtbot):
    """Panel should apply a stylesheet and respond to simulated theme change."""
    from gui.views.ingestion_lab_panel import IngestionLabPanel
    from gui.services.service_locator import services

    panel = IngestionLabPanel(base_dir="data")
    qtbot.addWidget(panel)
    # If theme_service present, stylesheet should not be empty (best-effort)
    ss = panel.styleSheet()
    assert isinstance(ss, str)
    # Simulate theme changed callback even if no keys changed
    panel.on_theme_changed(None, [])
    # Ensure property for reducedColor is set (0 or 1)
    val = panel.property("reducedColor")
    assert val in ("0", "1", None)  # property may be None if service absent

    # Basic filter invocation to ensure no exceptions with new styling
    panel.min_size.setValue(5)
    panel._apply_filters()
    panel.min_size.setValue(0)
    panel._apply_filters()
    assert panel.filtered_file_count() >= 0
