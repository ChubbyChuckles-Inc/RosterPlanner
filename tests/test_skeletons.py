from gui.design import (
    list_skeleton_variants,
    get_skeleton_variant,
    SkeletonVariant,
)
import pytest


def test_variant_names_present():
    names = [v.name for v in list_skeleton_variants()]
    for expected in ["table-row", "card", "chart-placeholder"]:
        assert expected in names


def test_variant_shapes_and_tokens():
    for v in list_skeleton_variants():
        assert isinstance(v, SkeletonVariant)
        assert v.duration_token in {"instant", "subtle", "pronounced"}
        assert v.easing_token in {"standard", "accelerate", "decelerate"}
        assert len(v.shapes) > 0
        for shape in v.shapes:
            assert shape["type"] in {"rect", "circle"}
            assert isinstance(shape["w"], int) and shape["w"] > 0
            assert isinstance(shape["h"], int) and shape["h"] > 0


def test_lookup_returns_same_object():
    a = get_skeleton_variant("card")
    b = get_skeleton_variant("card")
    assert a is b


def test_unknown_variant_raises():
    with pytest.raises(KeyError):
        get_skeleton_variant("nope")
