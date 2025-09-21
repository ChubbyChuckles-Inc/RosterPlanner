from src.gui.design import dpi_scaling_validation as dpi


def test_empty_samples():
    report = dpi.validate_scaling([])
    assert report.samples == ()
    assert report.issues == ()


def test_normal_samples_no_issues():
    samples = [
        dpi.DpiScaleSample("A", 1.0),
        dpi.DpiScaleSample("B", 1.25),
        dpi.DpiScaleSample("C", 1.5),
    ]
    report = dpi.validate_scaling(samples)
    assert report.list_errors() == []


def test_delta_excessive():
    samples = [dpi.DpiScaleSample("A", 1.0), dpi.DpiScaleSample("B", 2.0)]
    report = dpi.validate_scaling(samples)
    assert any(i.code == "delta-excessive" for i in report.issues)


def test_fractional_anomaly():
    samples = [dpi.DpiScaleSample("A", 1.0), dpi.DpiScaleSample("B", 1.3)]
    report = dpi.validate_scaling(samples)
    assert any(i.code == "fractional-anomaly" for i in report.issues)


def test_adjacent_gap():
    samples = [dpi.DpiScaleSample("A", 1.0), dpi.DpiScaleSample("B", 1.8)]
    report = dpi.validate_scaling(samples)
    assert any(i.code == "adjacent-gap" for i in report.issues)


def test_duplicate_redundancy_info():
    samples = [
        dpi.DpiScaleSample("A", 1.0),
        dpi.DpiScaleSample("B", 1.0),
        dpi.DpiScaleSample("C", 1.0),
        dpi.DpiScaleSample("D", 1.0),
        dpi.DpiScaleSample("E", 1.25),
    ]
    report = dpi.validate_scaling(samples)
    infos = report.list_info()
    assert any(i.code == "redundant" for i in infos)


def test_invalid_scale():
    try:
        dpi.DpiScaleSample("X", 0)
        assert False, "Expected ValueError"
    except ValueError:
        pass
    try:
        dpi.DpiScaleSample("Y", -1)
        assert False, "Expected ValueError"
    except ValueError:
        pass
