"""Tests for brand-neutral theme variant (Milestone 0.44)."""

from __future__ import annotations

from gui.design import load_tokens, ThemeManager


def test_brand_neutral_variant_overrides_some_groups():
    tokens = load_tokens()
    mgr = ThemeManager(tokens)
    default_map = dict(mgr.active_map())
    mgr.set_variant("brand-neutral")
    bn_map = dict(mgr.active_map())

    # Ensure background base changed (brand-neutral background applied)
    assert default_map["background.base"] != bn_map["background.base"]
    # Surface primary should also differ
    assert default_map["surface.primary"] != bn_map["surface.primary"]

    # Non-overridden semantic (e.g., border.focus) should persist
    assert default_map["border.focus"] == bn_map["border.focus"]

    # Switching back to default restores original values
    mgr.set_variant("default")
    restored = mgr.active_map()
    assert restored["background.base"] == default_map["background.base"]
    assert restored["surface.primary"] == default_map["surface.primary"]
