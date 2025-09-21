from gui.i18n.direction import (
    get_layout_direction,
    set_layout_direction,
    is_rtl,
)


def test_default_direction():
    assert get_layout_direction() == "ltr"
    assert not is_rtl()


def test_switch_to_rtl_and_back():
    set_layout_direction("rtl")
    assert get_layout_direction() == "rtl"
    assert is_rtl()
    set_layout_direction("ltr")
    assert get_layout_direction() == "ltr"
    assert not is_rtl()


def test_idempotent_and_invalid():
    set_layout_direction("rtl")
    set_layout_direction("rtl")  # idempotent
    try:
        set_layout_direction("bogus")
    except ValueError:
        pass
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected ValueError for invalid direction")
