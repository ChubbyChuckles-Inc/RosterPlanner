from __future__ import annotations

from gui.services.theme_service import ThemeService


def test_theme_service_generate_qss_variant_change():
    svc = ThemeService.create_default()
    base_qss = svc.generate_qss()
    assert "QMainWindow" in base_qss and len(base_qss) > 50
    # Ensure semantic aliases present
    colors = svc.colors()
    for key in ("background.primary", "background.secondary", "surface.card", "accent.base"):
        assert key in colors
    diff = svc.set_variant("high-contrast")
    if not diff.no_changes:
        new_qss = svc.generate_qss()
        assert new_qss != base_qss
        # Background lines differ
        assert "background: " in base_qss and "background: " in new_qss
