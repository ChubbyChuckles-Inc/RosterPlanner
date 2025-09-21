from gui.design import list_empty_states, get_empty_state, EmptyStateTemplate
import pytest


def test_registry_contains_core_templates():
    ids = [t.id for t in list_empty_states()]
    for expected in ["no-selection", "no-data", "search-empty", "error-generic"]:
        assert expected in ids


def test_templates_have_required_fields():
    for t in list_empty_states():
        assert isinstance(t, EmptyStateTemplate)
        assert t.id
        assert t.title
        assert t.message
        assert t.primary_action_hint
        assert t.icon
        assert t.severity in {"info", "warning", "error"}


def test_lookup_returns_same_object():
    a = get_empty_state("no-data")
    b = get_empty_state("no-data")
    assert a is b


def test_unknown_state_raises():
    with pytest.raises(KeyError):
        get_empty_state("does-not-exist")
