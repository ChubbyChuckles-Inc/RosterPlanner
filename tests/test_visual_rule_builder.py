"""Tests for Visual Rule Builder (Milestone 7.10.A1).

Focus: model compilation + integration toggle inside IngestionLabPanel.
"""

from __future__ import annotations

import pytest


def test_canvas_model_compile_basic():
    from gui.ingestion.visual_rule_builder import (
        CanvasModel,
        SelectorNode,
        FieldMappingNode,
        TransformChainNode,
    )

    model = CanvasModel()
    model.add_node(SelectorNode(id="sel1", kind="selector", label="Roster", selector="table.roster"))
    model.add_node(TransformChainNode(id="chain1", kind="transform_chain", label="Chain", transforms=["trim"]))
    model.add_node(
        FieldMappingNode(
            id="f1", kind="field", label="Name", field_name="name", selector="td.name"
        )
    )
    compiled = model.to_rule_set_mapping()
    assert "resources" in compiled
    res = list(compiled["resources"].values())[0]
    assert res["kind"] == "table"
    assert "columns" in res and res["columns"] == ["name"]


@pytest.mark.gui
def test_visual_builder_toggle_in_panel(qtbot, tmp_path):  # type: ignore
    from gui.views.ingestion_lab_panel import IngestionLabPanel

    panel = IngestionLabPanel(base_dir=str(tmp_path))
    qtbot.addWidget(panel)
    btn = panel.btn_visual_builder
    # Switch to visual builder
    btn.click()
    assert panel._editor_mode == 1
    # Add nodes via API (direct call avoids depending on button labels which may change)
    vb = panel.visual_builder
    vb._on_add_selector()
    vb._on_add_field()
    # Switch back (should inject snippet)
    btn.click()
    assert panel._editor_mode == 0
    text = panel.rule_editor.toPlainText()
    assert "Visual Builder Draft Resources" in text
    assert "selector" in text
