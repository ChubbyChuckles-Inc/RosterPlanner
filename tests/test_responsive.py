"""Tests for responsive breakpoints strategy (Milestone 0.21)."""

import pytest
from gui.design.responsive import list_breakpoints, get_breakpoint, classify_width, Breakpoint


def test_breakpoints_defined_and_ordered():
    bps = list_breakpoints()
    ids = [b.id for b in bps]
    assert ids == ["xs", "sm", "md", "lg", "xl"]
    # Ensure ascending min widths
    mins = [b.min_width for b in bps]
    assert mins == sorted(mins)


def test_classify_width_edges():
    # Inclusive lower bounds, exclusive upper bounds
    assert classify_width(0).id == "xs"
    assert classify_width(639).id == "xs"
    assert classify_width(640).id == "sm"
    assert classify_width(959).id == "sm"
    assert classify_width(960).id == "md"
    assert classify_width(1279).id == "md"
    assert classify_width(1280).id == "lg"
    assert classify_width(1599).id == "lg"
    assert classify_width(1600).id == "xl"
    assert classify_width(5000).id == "xl"


def test_negative_width_rejected():
    with pytest.raises(ValueError):
        classify_width(-1)


def test_specific_breakpoint_lookup():
    md = get_breakpoint("md")
    assert isinstance(md, Breakpoint)
    assert md.id == "md"
    assert md.min_width == 960


def test_unknown_breakpoint_raises():
    with pytest.raises(KeyError):
        get_breakpoint("mega")
