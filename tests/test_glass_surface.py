"""Tests for glass surface helper (Milestone 5.10.22)."""

from gui.design.glass_surface import (
    get_glass_capability,
    build_glass_qss,
    GlassCapability,
)


def test_capability_platform_whitelist():
    cap_win = get_glass_capability(override_platform="Windows")
    assert cap_win.supported and not cap_win.reduced_mode
    cap_linux = get_glass_capability(override_platform="Linux")
    assert not cap_linux.supported


def test_build_glass_enabled_and_disabled():
    enabled = GlassCapability(supported=True, reduced_mode=False)
    disabled = GlassCapability(
        supported=False, reduced_mode=False, reason="platform-not-whitelisted"
    )
    qss_enabled = build_glass_qss(
        "QWidget#GlassTest", "#223344", "#445566", intensity=30, capability=enabled
    )
    assert "rgba(" in qss_enabled and "glass disabled" not in qss_enabled
    qss_disabled = build_glass_qss(
        "QWidget#GlassTest", "#223344", "#445566", intensity=30, capability=disabled
    )
    assert "glass disabled" in qss_disabled and "rgba(" not in qss_disabled


def test_intensity_clamping():
    enabled = GlassCapability(supported=True, reduced_mode=False)
    qss_low = build_glass_qss(
        "QWidget#GlassLow", "#112233", "#334455", intensity=1, capability=enabled
    )
    # Expect at least 5% (alpha ~0.05 -> 0.05 in string)
    assert "0.05" in qss_low
    qss_high = build_glass_qss(
        "QWidget#GlassHigh", "#112233", "#334455", intensity=500, capability=enabled
    )
    # Expect clamped to <= 0.95
    assert "0.95" in qss_high
