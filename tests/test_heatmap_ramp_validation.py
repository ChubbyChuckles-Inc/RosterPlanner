from gui.design.heatmap_ramp_validation import validate_heatmap_ramp


def test_uniform_increasing_ramp():
    # Create a simple increasing lightness ramp (approx): dark -> mid -> light
    theme = {
        "heat.low": "#102030",
        "heat.mid": "#406080",
        "heat.high": "#a0c0e0",
    }
    report = validate_heatmap_ramp(["heat.low", "heat.mid", "heat.high"], theme)
    assert report.uniform is True
    assert report.reversals == 0
    assert report.missing == ()
    assert report.min_L < report.max_L


def test_non_monotonic_ramp_detects_reversal():
    theme = {
        "r1": "#101010",  # dark
        "r2": "#f0f0f0",  # light
        "r3": "#303030",  # darker again
    }
    report = validate_heatmap_ramp(["r1", "r2", "r3"], theme)
    assert report.uniform is False
    assert report.reversals >= 1


def test_short_ramp_edge_case():
    theme = {"only": "#222222", "second": "#444444"}
    report = validate_heatmap_ramp(["only", "second"], theme)
    assert report.uniform is False
    assert "short" in report.message.lower()


def test_missing_tokens_reported():
    theme = {"h1": "#000000"}
    report = validate_heatmap_ramp(["h1", "h2", "h3"], theme)
    assert report.uniform is False
    assert len(report.missing) == 2
    assert "missing" in report.message.lower()
