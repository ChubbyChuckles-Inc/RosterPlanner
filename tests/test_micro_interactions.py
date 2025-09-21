from gui.design import list_micro_interactions, get_micro_interaction, MicroInteraction
import pytest


def test_catalog_contains_expected_keys():
    names = [mi.name for mi in list_micro_interactions()]
    # Core set
    for expected in ["hover", "press", "selection", "drag-start", "drag-over", "drop"]:
        assert expected in names


def test_micro_interaction_fields():
    mi = get_micro_interaction("hover")
    assert isinstance(mi, MicroInteraction)
    assert mi.duration_token in {"instant", "subtle", "pronounced"}
    assert mi.easing_token in {"standard", "accelerate", "decelerate"}
    assert mi.intensity >= 1


def test_registry_sorted_iteration():
    names = [mi.name for mi in list_micro_interactions()]
    assert names == sorted(names)


def test_unknown_lookup_raises():
    with pytest.raises(KeyError):
        get_micro_interaction("nope")
