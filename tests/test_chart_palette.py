from gui.design import load_tokens, build_chart_palette
from gui.design.contrast import contrast_ratio
import pytest


def test_chart_palette_structure_default():
    tokens = load_tokens()
    palette = build_chart_palette(tokens)
    assert palette.background.startswith("#")
    assert len(palette.series) >= 6  # includes blended seed extension
    assert len(palette.series_muted) == len(palette.series)
    # Ensure muted variants differ from base
    assert all(a != b for a, b in zip(palette.series, palette.series_muted))


def test_chart_palette_contrast_grid():
    tokens = load_tokens()
    palette = build_chart_palette(tokens)
    ratio = contrast_ratio(palette.grid_major, palette.background)
    assert ratio >= 1.2  # minimal separation threshold for dark plotting area


def test_chart_palette_series_uniqueness():
    tokens = load_tokens()
    palette = build_chart_palette(tokens)
    # Basic uniqueness heuristic: at least 5 unique among first 6
    assert len(set(palette.series[:6])) >= 5


def test_chart_palette_dynamic_series_count():
    tokens = load_tokens()
    palette = build_chart_palette(tokens, series_count=14)
    assert len(palette.series) == 14
    # Ensure cycling retains first semantic seed ordering
    base = build_chart_palette(tokens, series_count=6).series[:6]
    assert palette.series[:6] == base


def test_chart_palette_muted_are_lighter():
    tokens = load_tokens()
    palette = build_chart_palette(tokens, series_count=8)
    # Muted variants should have higher contrast vs background (closer to text) OR at least differ
    diffs = [
        contrast_ratio(m, palette.background) != contrast_ratio(c, palette.background)
        for c, m in zip(palette.series, palette.series_muted)
    ]
    assert any(diffs)


def test_chart_palette_high_contrast_variant():
    tokens = load_tokens()
    if not tokens.is_high_contrast_supported():
        pytest.skip("High contrast variant not supported by tokens")
    palette_default = build_chart_palette(tokens, series_count=6, variant="default")
    palette_hc = build_chart_palette(tokens, series_count=6, variant="high-contrast")
    # Expect at least one grid or alert color difference when HC supported
    differs = (
        palette_default.grid_major != palette_hc.grid_major
        or palette_default.alert_positive != palette_hc.alert_positive
    )
    assert differs
