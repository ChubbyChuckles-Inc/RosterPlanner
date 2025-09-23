from gui.views.spacing_grid_overlay import (
    clamp_spacing,
    generate_grid_lines,
    MIN_SPACING,
    MAX_SPACING,
)


def test_clamp_spacing_bounds():
    assert clamp_spacing(MIN_SPACING - 10) == MIN_SPACING
    assert clamp_spacing(MAX_SPACING + 10) == MAX_SPACING
    mid = (MIN_SPACING + MAX_SPACING) // 2
    assert clamp_spacing(mid) == mid


def test_generate_grid_lines_basic():
    lines = generate_grid_lines(100, 50, 10)
    # Should include 0 and final position <= max(width,height)
    assert lines[0] == 0
    assert lines[-1] <= 100
    # Step should be uniform 10
    diffs = {b - a for a, b in zip(lines, lines[1:])}
    assert diffs == {10}


def test_generate_grid_lines_spacing_clamp():
    lines_small = generate_grid_lines(32, 32, 1)  # clamped to MIN_SPACING (>=2)
    assert lines_small[1] == MIN_SPACING
    lines_large = generate_grid_lines(128, 128, 999)
    # Only 0 and maybe one more if clamp < 128
    assert lines_large[0] == 0
    assert len(lines_large) >= 2  # at least one interval present
