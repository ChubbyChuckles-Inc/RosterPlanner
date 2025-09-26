"""Tests for Transform Palette (7.10.A3)."""

from __future__ import annotations


def test_add_transform_with_intelligent_defaults():
    from gui.ingestion.visual_rule_builder import CanvasModel, FieldMappingNode

    model = CanvasModel()
    field = FieldMappingNode(id="f1", kind="field", label="Field 1", field_name="col1", selector="td")
    model.add_node(field)
    # Add to_number should prepend trim
    applied = model.add_transform_to_field("f1", {"kind": "to_number"})
    assert applied is True
    kinds = [t["kind"] for t in field.transforms]
    assert kinds == ["trim", "to_number"]
    # Adding to_number again should not duplicate
    model.add_transform_to_field("f1", {"kind": "to_number"})
    kinds2 = [t["kind"] for t in field.transforms]
    assert kinds2 == ["trim", "to_number"]
    # Adding parse_date should not add duplicate trim
    model.add_transform_to_field("f1", {"kind": "parse_date", "format": "%Y-%m-%d"})
    kinds3 = [t["kind"] for t in field.transforms]
    assert kinds3 == ["trim", "to_number", "parse_date"]


def test_add_transform_no_field():
    from gui.ingestion.visual_rule_builder import CanvasModel

    model = CanvasModel()
    # No nodes present
    assert model.add_transform_to_field("missing", {"kind": "trim"}) is False