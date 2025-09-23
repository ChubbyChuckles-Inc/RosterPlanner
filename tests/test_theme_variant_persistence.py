from __future__ import annotations

from gui.app.bootstrap import create_app
from gui.services.service_locator import services
from gui.services.theme_service import ThemeService


def test_theme_variant_persistence(tmp_path):
    # First bootstrap: set variant to high-contrast
    ctx1 = create_app(headless=True, data_dir=str(tmp_path))
    svc1 = services.get_typed("theme_service", ThemeService)
    svc1.set_variant("high-contrast")
    # Second bootstrap: should retain high-contrast
    ctx2 = create_app(headless=True, data_dir=str(tmp_path))
    svc2 = services.get_typed("theme_service", ThemeService)
    assert svc2.manager.variant == "high-contrast"
