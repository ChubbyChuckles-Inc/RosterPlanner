"""Tests for adaptive accent contrast tuning (Milestone 5.10.24)."""

from gui.design.adaptive_contrast import ensure_accent_on_color
from gui.design.contrast import contrast_ratio


def test_adds_on_color_when_missing_low_contrast_dark_accent():
    mapping = {
        "accent.base": "#101030",  # dark-ish
    }
    ensure_accent_on_color(mapping)
    assert "accent.on" in mapping
    assert (
        contrast_ratio(mapping["accent.on"], mapping["accent.base"]) >= 4.0
    )  # may be >=4.5 typically


def test_preserves_existing_valid_on_color():
    mapping = {
        "accent.base": "#0055CC",
        "accent.on": "#FFFFFF",  # high contrast already
    }
    before = mapping["accent.on"]
    ensure_accent_on_color(mapping)
    assert mapping["accent.on"] == before


def test_overrides_insufficient_on_color():
    mapping = {
        "accent.base": "#E0E040",  # light accent
        "accent.on": "#FFFFEE",  # poor contrast
    }
    ensure_accent_on_color(mapping)
    assert contrast_ratio(mapping["accent.on"], mapping["accent.base"]) >= 4.0
