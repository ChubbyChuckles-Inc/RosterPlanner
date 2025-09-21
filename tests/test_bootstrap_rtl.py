from gui.app.bootstrap import parse_rtl, create_app
from gui.i18n.direction import get_layout_direction, set_layout_direction


def test_parse_rtl_flag_true():
    assert parse_rtl(["--rtl"]) is True
    assert parse_rtl(["--safe-mode"]) is False


def test_create_app_rtl_headless(monkeypatch):
    # Force headless so we don't require PyQt6 in test environment.
    from gui.app import bootstrap as bs

    monkeypatch.setattr(bs, "_QT_AVAILABLE", False, raising=True)
    # Reset direction to ltr first
    set_layout_direction("ltr")
    ctx = create_app(rtl=True, headless=True)
    assert ctx.metadata["layout_direction"] == "ltr"  # headless create_app does not apply (no qt)
    # Still, internal direction registry should reflect forced RTL when applied manually
    set_layout_direction("rtl")
    assert get_layout_direction() == "rtl"
