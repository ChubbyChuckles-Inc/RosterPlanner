from gui.design.glass_surface import adaptive_intensity, build_glass_qss, GlassCapability


def test_adaptive_intensity_dark():
    # Dark background should increase intensity
    base = 25
    new_val = adaptive_intensity(base, "#111111", luminance=0.05)
    assert new_val > base


def test_adaptive_intensity_bright():
    # Bright background should decrease intensity
    base = 25
    new_val = adaptive_intensity(base, "#FAFAFA", luminance=0.9)
    assert new_val < base


def test_adaptive_intensity_mid():
    base = 30
    # Mid luminance ~0.5 should produce small adjustment (abs <= 6)
    new_val = adaptive_intensity(base, "#777777", luminance=0.5)
    assert abs(new_val - base) <= 6


def test_build_glass_qss_adaptive_integration():
    cap = GlassCapability(supported=True, reduced_mode=False)
    qss = build_glass_qss(
        "QWidget#Test",
        "#202020",
        "#303030",
        intensity=25,
        adaptive=True,
        luminance=0.05,
        capability=cap,
    )
    assert "background:" in qss and "rgba" in qss  # translucency path
