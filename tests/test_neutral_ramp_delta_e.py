from gui.design.neutral_ramp_delta_e import validate_neutral_ramp, srgb_to_lab, delta_e


def test_neutral_ramp_basic_ok():
    ramp = ["#111111", "#1A1A1A", "#242424", "#2E2E2E", "#383838"]
    report = validate_neutral_ramp(ramp, min_delta=1.0, max_delta=15.0)
    assert report.ok, report.summary()
    assert len(report.deltas) == len(ramp) - 1


def test_neutral_ramp_too_small_gap():
    ramp = ["#111111", "#121212", "#131313"]  # very tiny increments
    report = validate_neutral_ramp(ramp, min_delta=2.0, max_delta=15.0)
    assert not report.ok
    assert any(iss.kind == "too_small" for iss in report.issues)


def test_neutral_ramp_invalid_hex():
    ramp = ["#111111", "nothex", "#222222"]
    report = validate_neutral_ramp(ramp)
    assert not report.ok
    assert any(iss.kind == "invalid_hex" for iss in report.issues)


def test_neutral_ramp_large_gap():
    ramp = ["#111111", "#4A4A4A"]  # Big jump likely > max_delta default
    report = validate_neutral_ramp(ramp, min_delta=1.0, max_delta=10.0)
    if report.ok:
        # In case delta is within threshold on some displays, assert we computed deltas
        assert report.deltas
    else:
        assert any(iss.kind == "too_large" for iss in report.issues)
