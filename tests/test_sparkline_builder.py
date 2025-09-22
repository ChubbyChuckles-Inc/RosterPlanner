from gui.services.sparkline import SparklineBuilder


def test_sparkline_empty():
    b = SparklineBuilder()
    assert b.build([]) == ""


def test_sparkline_single_value():
    b = SparklineBuilder()
    out = b.build([10])
    assert len(out) == 1
    assert out in SparklineBuilder._RAMP  # type: ignore


def test_sparkline_flat_sequence():
    b = SparklineBuilder()
    out = b.build([5, 5, 5])
    assert len(out) == 3
    # All chars identical
    assert len(set(out)) == 1


def test_sparkline_increasing_sequence():
    b = SparklineBuilder()
    out = b.build([1, 2, 3, 4, 5, 6, 7, 8])
    # Should be non-decreasing visually; ramp last char near the end
    assert len(out) == 8
    assert out[-1] in (SparklineBuilder._RAMP[-1], SparklineBuilder._RAMP[-2])  # type: ignore


def test_sparkline_varied_sequence():
    b = SparklineBuilder()
    values = [10, 3, 7, 15, 9]
    out = b.build(values)
    assert len(out) == len(values)
    # Should contain at least two distinct chars due to variance
    assert len(set(out)) >= 2
