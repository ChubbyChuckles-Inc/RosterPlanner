"""Tests for visual builder snippet injection & live preview (7.10.A1/A2)."""

from __future__ import annotations

import re


def _count_blocks(text: str) -> int:
    return len(re.findall(r"# --- Visual Builder Draft BEGIN ---", text))


def test_visual_builder_snippet_injection_no_duplicates(qtbot, tmp_path):  # type: ignore
    from gui.views.ingestion_lab_panel import IngestionLabPanel

    panel = IngestionLabPanel(base_dir=str(tmp_path))
    qtbot.addWidget(panel)
    panel.btn_visual_builder.click()  # open visual mode
    vb = panel.visual_builder
    vb._on_add_selector()
    vb._on_add_field()
    panel.btn_visual_builder.click()  # back to text
    t1 = panel.rule_editor.toPlainText()
    assert _count_blocks(t1) == 1
    # Toggle without changes
    panel.btn_visual_builder.click()
    panel.btn_visual_builder.click()
    t2 = panel.rule_editor.toPlainText()
    assert _count_blocks(t2) == 1


def test_visual_builder_live_preview_updates_single_block(qtbot, tmp_path):  # type: ignore
    from gui.views.ingestion_lab_panel import IngestionLabPanel

    panel = IngestionLabPanel(base_dir=str(tmp_path))
    qtbot.addWidget(panel)
    panel.btn_visual_builder.click()
    vb = panel.visual_builder
    vb.chk_live.setChecked(True)
    vb._on_add_selector()
    vb._on_add_field()
    # Should inject while still open (signal)
    panel.btn_visual_builder.click()
    t1 = panel.rule_editor.toPlainText()
    assert _count_blocks(t1) == 1
    panel.btn_visual_builder.click()
    vb._on_add_field()
    panel.btn_visual_builder.click()
    t2 = panel.rule_editor.toPlainText()
    assert _count_blocks(t2) == 1