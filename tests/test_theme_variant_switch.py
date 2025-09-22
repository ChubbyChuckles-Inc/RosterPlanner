from gui.services.theme_service import ThemeService


def test_theme_variant_cycle():
    svc = ThemeService.create_default()
    base_map = dict(svc.colors())
    diff_brand = svc.set_variant("brand-neutral")
    assert not diff_brand.no_changes
    assert svc.colors() != base_map
    diff_high = svc.set_variant("high-contrast")
    assert not diff_high.no_changes
    # switching back to same variant should yield no change diff
    diff_repeat = svc.set_variant("high-contrast")
    assert diff_repeat.no_changes
