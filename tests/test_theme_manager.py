from __future__ import annotations

from gui.design import load_tokens
from gui.design.theme_manager import ThemeManager


def test_theme_manager_variant_switch_diff():
    tm = ThemeManager(load_tokens())
    base_map = dict(tm.active_map())
    diff = tm.set_variant("high-contrast")
    assert not diff.no_changes
    assert any(k.startswith("background.") for k in diff.changed.keys())
    # A second call with same variant should yield no diff
    diff2 = tm.set_variant("high-contrast")
    assert diff2.no_changes
    # Ensure accent keys still present
    assert any(
        k.startswith("accent.primary") or k == "accent.primary" for k in tm.active_map().keys()
    )


def test_theme_manager_accent_change_affects_only_accent_keys():
    tm = ThemeManager(load_tokens())
    old = dict(tm.active_map())
    diff = tm.set_accent_base("#FF5722")
    assert not diff.no_changes
    # Non-accent keys should remain same
    for k, (ov, nv) in diff.changed.items():
        if not k.startswith("accent."):
            # Allow background.* changes only if variant changed (it did not)
            assert k.startswith("accent."), f"Unexpected non-accent change: {k}"
