from gui.design.ambient_color_shift import (
    set_ambient_shift_enabled,
    compute_shifted_hex,
)


def test_ambient_shift_disabled_returns_original():
    set_ambient_shift_enabled(False)
    base = "#336699"
    c1 = compute_shifted_hex(base, now=0.0, period_seconds=10)
    c2 = compute_shifted_hex(base, now=5.0, period_seconds=10)
    assert c1 == base and c2 == base


def test_ambient_shift_changes_color():
    set_ambient_shift_enabled(True)
    base = "#336699"
    c1 = compute_shifted_hex(base, now=0.0, period_seconds=40, amplitude_degrees=60)
    c2 = compute_shifted_hex(base, now=10.0, period_seconds=40, amplitude_degrees=60)
    assert c1 != c2
    assert c1.startswith("#") and len(c1) == 7
    assert c2.startswith("#") and len(c2) == 7


def test_ambient_shift_periodic_symmetry():
    set_ambient_shift_enabled(True)
    base = "#336699"
    c_mid = compute_shifted_hex(base, now=5.0, period_seconds=20, amplitude_degrees=40)
    c_mid2 = compute_shifted_hex(base, now=15.0, period_seconds=20, amplitude_degrees=40)
    # Sine wave symmetry: phase 0.25 and 0.75 should produce opposite sign, but not equal – ensure both differ from base
    assert c_mid != base and c_mid2 != base and c_mid != c_mid2
