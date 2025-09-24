from gui.services.reduced_color_mode_service import ReducedColorModeService


def test_grayscale_basic():
    svc = ReducedColorModeService()
    # Pure red -> luminance ~ 54
    g = svc.grayscale_hex("#ff0000")
    assert g.startswith("#") and len(g) == 7
    # All channels equal
    v = g[1:]
    assert v[0:2] == v[2:4] == v[4:6]


def test_transform_mapping():
    svc = ReducedColorModeService()
    result = svc.transform_mapping({"a": "#000000", "b": "#ffffff", "c": "#123456"})
    assert set(result.keys()) == {"a", "b", "c"}
    for val in result.values():
        assert len(val) == 7 and val.startswith("#")


def test_toggle_and_snippet():
    svc = ReducedColorModeService()
    assert not svc.is_active()
    assert svc.neutral_qss_snippet() == ""
    svc.set_active(True)
    assert svc.is_active()
    snippet = svc.neutral_qss_snippet()
    assert "Reduced Color Mode Overrides" in snippet
