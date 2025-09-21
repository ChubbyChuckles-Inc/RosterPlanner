import pytest
from gui.design.focus_ring import build_focus_ring_style, contrast_ratio


def test_focus_ring_basic():
    style = build_focus_ring_style(
        desired_color="#3366FF", background_color="#FFFFFF", inner_width_px=2, outer_width_px=2
    )
    assert style.primary_color == "#3366FF"
    assert style.inner_width_px == 2
    assert style.outer_width_px == 2
    assert style.contrast_ratio >= 3.0  # sufficient contrast on white


def test_focus_ring_adjusts_low_contrast():
    # Light gray on white -> low contrast, should flip to black or white whichever higher (likely black)
    style = build_focus_ring_style(
        desired_color="#EEEEEE", background_color="#FFFFFF", min_contrast=3.0
    )
    assert style.effective_color in {"#000000", "#FFFFFF"}
    # Ensure ratio was raised sufficiently
    assert style.contrast_ratio >= 3.0


def test_invalid_hex():
    with pytest.raises(ValueError):
        build_focus_ring_style(desired_color="blue", background_color="#FFFFFF")


def test_invalid_widths():
    with pytest.raises(ValueError):
        build_focus_ring_style(
            desired_color="#000000", background_color="#FFFFFF", inner_width_px=0
        )
    with pytest.raises(ValueError):
        build_focus_ring_style(
            desired_color="#000000", background_color="#FFFFFF", outer_width_px=-1
        )


def test_outer_opacity_range():
    with pytest.raises(ValueError):
        build_focus_ring_style(
            desired_color="#000000", background_color="#FFFFFF", outer_opacity=1.5
        )
