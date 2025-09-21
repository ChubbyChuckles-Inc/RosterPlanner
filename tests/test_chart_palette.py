from gui.design import load_tokens, build_chart_palette
from gui.design.contrast import contrast_ratio


def test_chart_palette_structure():
    tokens = load_tokens()
    palette = build_chart_palette(tokens)
    assert palette.background.startswith("#")
    assert len(palette.series) >= 5
    assert len(palette.series_muted) == len(palette.series)
    # Ensure muted variants differ from base
    diffs = [a != b for a, b in zip(palette.series, palette.series_muted)]
    assert all(diffs)


def test_chart_palette_contrast_grid():
    tokens = load_tokens()
    palette = build_chart_palette(tokens)
    ratio = contrast_ratio(palette.grid_major, palette.background)
    assert ratio >= 1.2  # minimal separation threshold for dark plotting area


def test_chart_palette_series_uniqueness():
    tokens = load_tokens()
    palette = build_chart_palette(tokens)
    # Basic uniqueness heuristic: at least 4 unique colors among first 5
    assert len(set(palette.series[:5])) >= 4
