from gui.viewmodels.theme_preview_diff_viewmodel import ThemePreviewDiffViewModel
from gui.services.theme_service import ThemeService


def test_theme_preview_variant_diff_generates_changes():
    svc = ThemeService.create_default()
    vm = ThemePreviewDiffViewModel.capture(svc)
    entries = vm.simulate_variant("high-contrast")
    assert entries, "Expected some changes when simulating high-contrast variant"
    # Ensure tuple format (key, old, new) and no identical entries
    for k, old, new in entries[:10]:
        assert old != new
        assert k


def test_theme_preview_accent_diff_changes_accent_keys():
    svc = ThemeService.create_default()
    vm = ThemePreviewDiffViewModel.capture(svc)
    entries = vm.simulate_accent("#AA3377")
    keys = {k for k, *_ in entries}
    assert any(k.startswith("accent.") for k in keys)
