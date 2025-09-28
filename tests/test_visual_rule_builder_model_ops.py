import pytest

from src.gui.ingestion.visual_rule_builder import (
    CanvasModel,
    FieldMappingNode,
    SelectorNode,
    TransformChainNode,
)


def build_basic_model():
    model = CanvasModel()
    model.add_node(SelectorNode(id="selector1", kind="selector", label="Sel1", selector="table"))
    model.add_node(
        FieldMappingNode(
            id="field1", kind="field", label="Field1", field_name="f1", selector="td.name"
        )
    )
    model.add_node(
        FieldMappingNode(
            id="field2", kind="field", label="Field2", field_name="f2", selector="td.score"
        )
    )
    model.add_node(
        TransformChainNode(
            id="chain1", kind="transform_chain", label="Chain1", transforms=[{"kind": "trim"}]
        )
    )
    return model


def test_duplicate_field_node_unique_ids():
    model = build_basic_model()
    dup = model.duplicate_node("field1")
    assert dup is not None
    assert dup.id != "field1"
    assert dup.id.startswith("field1_")
    # Field name adjusted
    assert dup.field_name != "f1"
    assert dup.field_name.startswith("f1_")
    # Model size + order
    assert [n.id for n in model.nodes][1:3] == ["field1", dup.id]


def test_reorder_after_manual_list_shuffle():
    model = build_basic_model()
    # Simulate drag reorder by manipulating underlying list order (GUI does mapping)
    model.nodes = [model.nodes[0], model.nodes[2], model.nodes[1], model.nodes[3]]
    mapping = model.to_rule_set_mapping()
    # Order of field addition affects compiled resource columns (table mode)
    resources = mapping["resources"]
    res = next(iter(resources.values()))
    assert res["columns"] == ["f2", "f1"]


def test_transform_intelligent_prereq():
    model = CanvasModel()
    f = FieldMappingNode(id="f", kind="field", label="F", field_name="value", selector="td")
    model.add_node(SelectorNode(id="s", kind="selector", label="Sel", selector="table"))
    model.add_node(f)
    applied = model.add_transform_to_field("f", {"kind": "to_number"})
    assert applied is True
    assert [t["kind"] for t in f.transforms] == ["trim", "to_number"]


def test_promote_transform_chain_to_macro():
    model = CanvasModel()
    selector = SelectorNode(
        id="s",
        kind="selector",
        label="Roster",
        selector="div.roster",
        mode="list",
        item_selector="div.player",
    )
    field1 = FieldMappingNode(
        id="f1",
        kind="field",
        label="Points",
        field_name="points",
        selector="td.points",
        transforms=[{"kind": "trim"}, {"kind": "to_number"}],
    )
    field2 = FieldMappingNode(
        id="f2",
        kind="field",
        label="Bonus",
        field_name="bonus",
        selector="td.bonus",
        transforms=[{"kind": "trim"}, {"kind": "to_number"}],
    )
    model.add_node(selector)
    model.add_node(field1)
    model.add_node(field2)

    promoted = model.promote_transform_chain_to_macro("CleanNumber", ["f1", "f2"])
    assert promoted is True
    assert "CleanNumber" in model.macros
    assert model.macros["CleanNumber"] == [{"kind": "trim"}, {"kind": "to_number"}]
    assert field1.transforms == [] and field2.transforms == []
    assert field1.macros == ["CleanNumber"] and field2.macros == ["CleanNumber"]

    usage = model.macro_usage_counts()
    assert usage["CleanNumber"] == 2

    compiled = model.to_rule_set_mapping()
    assert "transform_macros" in compiled
    assert compiled["transform_macros"]["CleanNumber"][0]["kind"] == "trim"
    fields = compiled["resources"]["Roster"]["fields"]
    assert fields["points"]["macros"] == ["CleanNumber"]
    assert "transforms" not in fields["points"]
    assert compiled["macro_usage"]["CleanNumber"] == 2


def test_promote_macro_requires_matching_chain():
    model = CanvasModel()
    selector = SelectorNode(id="s", kind="selector", label="Roster", selector="table")
    field1 = FieldMappingNode(
        id="f1",
        kind="field",
        label="Points",
        field_name="points",
        selector="td.points",
        transforms=[{"kind": "trim"}, {"kind": "to_number"}],
    )
    field2 = FieldMappingNode(
        id="f2",
        kind="field",
        label="Name",
        field_name="name",
        selector="td.name",
        transforms=[{"kind": "trim"}],
    )
    model.add_node(selector)
    model.add_node(field1)
    model.add_node(field2)
    with pytest.raises(ValueError):
        model.promote_transform_chain_to_macro("MacroX", ["f1", "f2"])
