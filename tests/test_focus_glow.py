from gui.design.focus_ring_glow import build_focus_glow_qss
from gui.design.reduced_motion import temporarily_reduced_motion


def test_focus_glow_basic():
    snippet = build_focus_glow_qss(
        "#336699", radius_px=3, spread_px=2, opacity=0.4, reduced_motion=False, high_contrast=False
    )
    assert "outline:" in snippet
    assert "border-radius:" in snippet


def test_focus_glow_reduced_motion_disabled():
    with temporarily_reduced_motion(True):
        snippet = build_focus_glow_qss("#336699", reduced_motion=None)
        assert snippet == ""


def test_focus_glow_high_contrast_disabled():
    snippet = build_focus_glow_qss("#336699", high_contrast=True)
    assert snippet == ""


def test_focus_glow_opacity_applied():
    snippet = build_focus_glow_qss("#112233", opacity=0.5, reduced_motion=False)
    # Alpha 0.5 -> 0x80
    assert "#11223380" in snippet


def test_invalid_params():
    try:
        build_focus_glow_qss("112233")
        assert False, "Expected color validation"
    except ValueError:
        pass
    try:
        build_focus_glow_qss("#112233", opacity=1.5)
        assert False, "Expected opacity validation"
    except ValueError:
        pass
