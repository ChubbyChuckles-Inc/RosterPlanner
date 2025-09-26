import os, json
import pytest
from PyQt6.QtWidgets import QApplication

# Ensure headless
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("RP_TEST_MODE", "1")

app = QApplication.instance() or QApplication([])


def _build_min_rules():
    return {
        "version": 1,
        "resources": {
            "sample": {
                "kind": "list",
                "selector": "body",
                "item_selector": "div",
                "fields": {"text": {"selector": "div"}},
            }
        },
    }


def test_keyboard_shortcuts_registration_and_preview(tmp_path, qtbot):
    # Arrange sample data directory with single html file
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    html_file = data_dir / "sample_asset.html"
    html_file.write_text("<html><body><div>Alpha</div></body></html>", encoding="utf-8")

    from gui.views.ingestion_lab_panel import IngestionLabPanel
    from gui.services.shortcut_registry import global_shortcut_registry

    panel = IngestionLabPanel(base_dir=str(data_dir))
    qtbot.addWidget(panel)

    # Act: ensure file list populated and select first leaf item
    panel.refresh_file_list()
    # Find first actual file child
    first_child = None
    for r in range(panel.file_tree.topLevelItemCount()):
        phase_item = panel.file_tree.topLevelItem(r)
        if phase_item.childCount():
            first_child = phase_item.child(0)
            break
    assert first_child is not None, "Expected at least one file child in tree"
    panel.file_tree.setCurrentItem(first_child)

    # Validate shortcuts registered in registry (logical ids)
    expected_ids = {
        "ing.refresh",
        "ing.preview",
        "ing.search",
        "ing.simulate",
        "ing.apply",
        "ing.security",
        "ing.export",
        "ing.import",
        "ing.hash_impact",
    }
    registered_ids = {
        e.shortcut_id for e in global_shortcut_registry.list() if e.category == "Ingestion Lab"
    }
    # Subset check: some ids from other tests may already exist; ensure ours are present
    missing = expected_ids - registered_ids
    assert not missing, f"Missing expected shortcut registrations: {missing}"

    # Put minimal valid rules into the editor so simulation won't error if triggered
    panel.rule_editor.setPlainText(json.dumps(_build_min_rules()))

    # Dispatch preview via dispatcher directly (simulating Enter or shortcut activation)
    panel._dispatch_shortcut("ing.preview")
    preview_text = panel.preview_area.toPlainText()
    assert "sample_asset.html" in preview_text or "Alpha" in preview_text

    # Dispatch refresh
    panel._dispatch_shortcut("ing.refresh")
    # If no exception, log should contain Refreshed line
    log_text = panel.log_area.toPlainText()
    assert "Refreshed:" in log_text


def test_enter_key_triggers_preview(tmp_path, qtbot):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "ranking_table_test.html").write_text(
        "<html><body>RT</body></html>", encoding="utf-8"
    )

    from gui.views.ingestion_lab_panel import IngestionLabPanel
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QKeyEvent

    panel = IngestionLabPanel(base_dir=str(data_dir))
    qtbot.addWidget(panel)
    panel.refresh_file_list()

    # Select first child
    first_child = None
    for r in range(panel.file_tree.topLevelItemCount()):
        phase_item = panel.file_tree.topLevelItem(r)
        if phase_item.childCount():
            first_child = phase_item.child(0)
            break
    assert first_child is not None
    panel.file_tree.setCurrentItem(first_child)

    # Send Return key event directly to tree
    # PyQt6 uses enum scoping (Qt.Key.Key_Return). Fallback to Enter if needed.
    key = getattr(Qt.Key, "Key_Return", getattr(Qt.Key, "Key_Enter", None))
    assert key is not None, "Qt Key_Return not available"
    event = QKeyEvent(QKeyEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)
    panel.file_tree.keyPressEvent(event)  # type: ignore

    preview_text = panel.preview_area.toPlainText()
    assert "ranking_table_test" in preview_text or "RT" in preview_text
