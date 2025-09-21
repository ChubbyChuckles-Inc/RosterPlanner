import pytest

from src.gui.design import cursor_affordance as ca


def test_defaults_idempotent():
    ca.clear_cursor_affordances()
    first = ca.ensure_default_cursor_affordances()
    second = ca.ensure_default_cursor_affordances()
    assert first > 0
    assert second == 0  # already loaded


def test_registry_basic_lookup():
    ca.clear_cursor_affordances()
    ca.ensure_default_cursor_affordances()
    aff = ca.get_cursor_affordance("resize-ew")
    assert aff is not None
    assert aff.qt_cursor_name == "SizeHorCursor"


def test_register_duplicate_error():
    ca.clear_cursor_affordances()
    ca.ensure_default_cursor_affordances()
    existing = ca.list_cursor_affordances()[0]
    with pytest.raises(ValueError):
        ca.register_cursor_affordance(existing)


def test_clear_then_re_register():
    ca.clear_cursor_affordances()
    assert ca.list_cursor_affordances() == []
    ca.ensure_default_cursor_affordances()
    assert len(ca.list_cursor_affordances()) > 0


def test_invalid_metadata():
    from src.gui.design.cursor_affordance import CursorAffordance

    with pytest.raises(ValueError):
        CursorAffordance("", "desc", "ArrowCursor")
    with pytest.raises(ValueError):
        CursorAffordance("id", "", "ArrowCursor")
    with pytest.raises(ValueError):
        CursorAffordance("id", "desc", "")
