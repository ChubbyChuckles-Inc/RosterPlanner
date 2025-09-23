import os
import json
from pathlib import Path
import pytest
from gui.testing.visual_regression import capture_widget_screenshot, hash_image_bytes
from gui.components.empty_state import EmptyStateWidget

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

@pytest.mark.gui
def test_empty_state_baseline_match(qtbot):
    widget = EmptyStateWidget('no_division_rows')
    qtbot.addWidget(widget)
    data = capture_widget_screenshot(lambda: widget, size=(320,140))
    h = hash_image_bytes(data)
    meta_path = Path('tests/_visual_baseline/core/empty_state_no_division_rows.json')
    assert meta_path.exists(), "Baseline metadata missing; run scripts/dump_visual_baselines.py"
    baseline_hash = json.loads(meta_path.read_text())['hash']
    assert h == baseline_hash, f"Hash mismatch: {h} != {baseline_hash}. If intentional UI change, regenerate baselines."
